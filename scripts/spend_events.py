#!/usr/bin/env python3
"""Detect notable events in a run's daily spend series and write reports/spend-events.json.

Usage:
    python scripts/spend_events.py .finops/runs/<id>/ [--events .finops/events.json]
                                   [--out <file>] [--min-daily 1.0]

Reads `spend.json` (the optional `daily` block), `iteration.json` (window boundaries) and an
optional manual `.finops/events.json`; writes `<run>/reports/spend-events.json`. It never calls
Azure. The detection functions are pure so the dashboard can reuse them.

Detected events, per service (the "Other" bucket is ignored), on SETTLED days only (the last three
days of the window are provisional and never used):

- `stopped`     >= 7 days of spend, then >= 3 days of zero spend.
- `started`     >= 7 days of zero spend, then >= 3 days of spend.
- `step-change` the 7-day mean shifts by >= 30% and stays shifted for >= 5 days.
- `spike`       a day beyond 3 sigma of the trailing 14 days, and at least MIN_SPIKE above their
                mean (and a typical day must itself be material), lasting no more than 3 days (longer is a
                step change).

A service must be material (at least `min_daily` per day on the relevant side of the event).
Amounts stay in the series' own currency; nothing is converted or combined across currencies.

Each event is {date, service, kind, before, after, currency, source} (`before`/`after` are daily
averages; `source` is "detected", "manual" or "iteration"), plus an optional `note`.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import spend_daily as sd

THRESHOLDS = {
    "min_daily": 1.0,  # a service must bill at least this much per day to be material
    "min_run_days": 7,  # days of spend (stopped) / zero spend (started) before the change
    "confirm_days": 3,  # days the new state must hold for stopped / started
    "shift_pct": 0.30,  # step-change: relative shift of the 7-day mean
    "shift_days": 5,  # step-change: days the shift must be sustained
    "spike_sigma": 3.0,
    "spike_window": 14,  # trailing days used for the spike baseline
    "min_spike": 5.0,  # a spike must exceed the trailing mean by at least this much
    "max_spike_days": 3,  # a longer excursion is a step change, not a spike
}
ZERO = 0.005  # at or below this a day counts as "no spend"
MEAN_DAYS = 7
MANUAL_KIND = re.compile(r"^[a-z][a-z0-9-]{0,29}$")
MAX_NOTE = 200


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _event(day: date, service, kind: str, before, after, currency, source="detected", note=None):
    ev = {
        "date": day.isoformat(),
        "service": service,
        "kind": kind,
        "before": None if before is None else round(before, 2),
        "after": None if after is None else round(after, 2),
        "currency": currency,
        "source": source,
    }
    if note:
        ev["note"] = note
    return ev


def _segments(values: list[float]) -> list[tuple[bool, int, int]]:
    """Runs of (is_zero, start, end) with end inclusive."""
    out: list[tuple[bool, int, int]] = []
    for i, v in enumerate(values):
        zero = v <= ZERO
        if out and out[-1][0] == zero:
            out[-1] = (zero, out[-1][1], i)
        else:
            out.append((zero, i, i))
    return out


def detect_service_events(
    service: str, days: list[date], values: list[float], currency: str, **overrides
) -> list[dict]:
    """Events for one service over its settled daily values (oldest first)."""
    cfg = {**THRESHOLDS, **overrides}
    n = len(values)
    if n == 0 or max(values) < cfg["min_daily"]:
        return []
    events: list[dict] = []
    near: set[int] = set()  # indexes too close to a stop/start/step to also report a step/spike

    def block(i: int, width: int = MEAN_DAYS) -> None:
        near.update(range(max(0, i - width), min(n, i + width + 1)))

    segs = _segments(values)
    for k, (zero, start, end) in enumerate(segs):
        nxt = segs[k + 1] if k + 1 < len(segs) else None
        length = end - start + 1
        if not zero and length >= cfg["min_run_days"] and nxt and nxt[0]:
            if nxt[2] - nxt[1] + 1 >= cfg["confirm_days"]:
                before = _mean(values[max(start, end - MEAN_DAYS + 1) : end + 1])
                if before >= cfg["min_daily"]:
                    events.append(_event(days[nxt[1]], service, "stopped", before, 0.0, currency))
                    block(nxt[1])
        if zero and length >= cfg["min_run_days"] and nxt and not nxt[0]:
            if nxt[2] - nxt[1] + 1 >= cfg["confirm_days"]:
                after = _mean(values[nxt[1] : nxt[1] + MEAN_DAYS])
                if after >= cfg["min_daily"]:
                    events.append(_event(days[nxt[1]], service, "started", 0.0, after, currency))
                    block(nxt[1])

    # step-change: 7-day mean shifts >= shift_pct and stays shifted for shift_days days
    half = cfg["shift_pct"] / 2
    i = MEAN_DAYS
    while i <= n - cfg["shift_days"]:
        if i in near:
            i += 1
            continue
        before = _mean(values[i - MEAN_DAYS : i])
        window = values[i : i + MEAN_DAYS]
        after = _mean(window)
        if before >= cfg["min_daily"] and abs(after - before) / before >= cfg["shift_pct"]:
            up = after > before
            first = values[i : i + cfg["shift_days"]]
            beyond = (lambda v: v >= before * (1 + half)) if up else (lambda v: v <= before * (1 - half))
            behind = values[i - 1] < before * (1 + half) if up else values[i - 1] > before * (1 - half)
            if all(beyond(v) for v in first) and behind:
                events.append(_event(days[i], service, "step-change", before, after, currency))
                block(i)
                i += MEAN_DAYS
                continue
        i += 1

    # spike: beyond sigma * trailing 14 days and min_spike above their mean, lasting <= 3 days
    w = cfg["spike_window"]
    i = w
    while i < n:
        if i in near:
            i += 1
            continue
        trailing = values[i - w : i]
        mu, sigma = _mean(trailing), statistics.pstdev(trailing)
        limit = mu + max(cfg["spike_sigma"] * sigma, cfg["min_spike"])
        # a typical (median) day below min_daily means the service was effectively off: a start
        if values[i] > limit and values[i] >= cfg["min_daily"] and statistics.median(trailing) >= cfg["min_daily"]:
            run = 1
            while i + run < n and values[i + run] > limit:
                run += 1
            if run <= cfg["max_spike_days"]:
                events.append(_event(days[i], service, "spike", mu, values[i], currency))
            i += run
            continue
        i += 1
    return sorted(events, key=lambda e: (e["date"], e["kind"]))


# --------------------------------------------------------------------- manual / iteration
def load_manual_events(path: Path | None) -> tuple[list[dict], list[str]]:
    """Read `.finops/events.json` ([{date, label|note, service?, kind?}] or {"events": [...]})."""
    if path is None or not Path(path).is_file():
        return [], []
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [], [f"events file ignored: {exc}"]
    items = doc.get("events") if isinstance(doc, dict) else doc
    if not isinstance(items, list):
        return [], ["events file ignored: expected an array of events"]
    return [i for i in items if i is not None], []


def _manual_events(items: list, window: tuple[date, date], currency: str) -> tuple[list[dict], list[str]]:
    events, warnings = [], []
    for idx, item in enumerate(items):
        day = sd.parse_date(item.get("date")) if isinstance(item, dict) else None
        text = item.get("label") or item.get("note") if isinstance(item, dict) else None
        if day is None or not isinstance(text, str) or not text.strip():
            warnings.append(f"manual event {idx} skipped: needs a valid 'date' and a 'label'")
            continue
        if not window[0] <= day <= window[1]:
            warnings.append(f"manual event {idx} ({day}) is outside the daily window; not plotted")
            continue
        kind = item.get("kind")
        kind = kind if isinstance(kind, str) and MANUAL_KIND.match(kind) else "manual"
        service = item.get("service")
        events.append(
            _event(
                day, service if isinstance(service, str) and service else None, kind, None, None,
                currency, "manual", text.strip()[:MAX_NOTE],
            )
        )
    return events, warnings


def _iteration_events(iteration: dict | None, window: tuple[date, date], currency: str) -> list[dict]:
    if not isinstance(iteration, dict):
        return []
    span = iteration.get("measurementWindow") or {}
    name = str(iteration.get("iterationId") or "iteration")[:60]
    out = []
    for key, kind, verb in (("from", "iteration-start", "starts"), ("to", "iteration-end", "ends")):
        day = sd.parse_date(span.get(key))
        if day and window[0] <= day <= window[1]:
            out.append(_event(day, None, kind, None, None, currency, "iteration", f"{name} {verb}"))
    return out


# ------------------------------------------------------------------------------ main API
def detect_events(
    spend: dict,
    iteration: dict | None = None,
    manual: list | None = None,
    **overrides,
) -> dict:
    """Events for a run, as a report dict. `available` is False when there is no daily series."""
    cfg = {**THRESHOLDS, **overrides}
    daily = sd.get_daily(spend)
    if daily is None:
        return {"available": False, "events": [], "warnings": [], "thresholds": cfg}
    currency = daily.get("currency") or spend.get("currency")
    start, end = sd.window(daily)
    settled = sd.settled_through(daily)
    days = [d for d in sd.all_dates(daily) if d <= settled]
    events: list[dict] = []
    for service, by_day in sd.series_by_service(daily).items():
        if service == sd.OTHER:
            continue
        events += detect_service_events(
            service, days, [by_day.get(d, 0.0) for d in days], currency, **overrides
        )
    manual_events, warnings = _manual_events(manual or [], (start, end), currency)
    events += manual_events + _iteration_events(iteration, (start, end), currency)
    events.sort(key=lambda e: (e["date"], e["service"] or "", e["kind"]))
    return {
        "available": True,
        "currency": currency,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "settledThrough": settled.isoformat(),
        "thresholds": cfg,
        "events": events,
        "warnings": warnings,
    }


def event_magnitude(event: dict) -> float:
    """Size of the change in the event's own currency per day (0 for notes and boundaries)."""
    if event.get("before") is None or event.get("after") is None:
        return 0.0
    return abs(event["after"] - event["before"])


def describe_event(event: dict) -> str:
    """One plain-English line for an event (used for chart labels and the Executive view)."""
    service = event.get("service") or "Spend"
    kind = event.get("kind")
    if kind == "stopped":
        return f"{service} charges stopped"
    if kind == "started":
        return f"{service} charges started"
    if kind == "step-change":
        rose = (event.get("after") or 0) > (event.get("before") or 0)
        return f"{service} charges {'rose' if rose else 'fell'}"
    if kind == "spike":
        return f"{service} had a one-day spike"
    return event.get("note") or "Event noted"


def build_report(run: Path, events_path: Path | None, now: datetime | None = None, **overrides) -> dict:
    spend = _read(run / "spend.json") or {}
    iteration = _read(run / "iteration.json")
    manual, load_warnings = load_manual_events(events_path)
    report = detect_events(spend, iteration, manual, **overrides)
    report["warnings"] = load_warnings + report.get("warnings", [])
    report["generatedAt"] = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    report["runId"] = run.name
    return report


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Detect events in a run's daily spend series.")
    parser.add_argument("run", type=Path, help=".finops/runs/<id>/")
    parser.add_argument("--events", type=Path, default=None, help="manual events file")
    parser.add_argument("--out", type=Path, default=None, help="output file")
    parser.add_argument("--min-daily", type=float, default=THRESHOLDS["min_daily"])
    args = parser.parse_args(argv[1:])
    run = args.run
    if not (run / "spend.json").is_file():
        print(f"ERROR: {run / 'spend.json'} not found", file=sys.stderr)
        return 1
    events_path = args.events or run.resolve().parent.parent / "events.json"
    report = build_report(run, events_path, min_daily=args.min_daily)
    out = args.out or run / "reports" / "spend-events.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["available"]:
        print("No daily spend series in spend.json - wrote an empty events report. Re-run Discovery.")
    else:
        print(f"{len(report['events'])} event(s) written to {out}")
        for ev in report["events"]:
            print(f"  {ev['date']}  {describe_event(ev)}  [{ev['source']}]")
    for w in report["warnings"]:
        print(f"WARNING: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
