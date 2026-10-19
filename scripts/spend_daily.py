"""Pure helpers for the optional daily spend series (`spend.json` -> `daily`).

No Streamlit, no Azure, no file writes. Shared by the Discovery validator, the event detector, the
chart builders and the dashboard so they all read the series the same way.

Money here is always in the single currency the Cost Management API returned for this run; nothing
in this module converts or combines currencies. Cost data lags by up to ~3 days, so the last
PROVISIONAL_DAYS days of a window are "provisional" (still settling).
"""
from __future__ import annotations

from datetime import date, timedelta

OTHER = "Other"
PROVISIONAL_DAYS = 3
RECONCILE_TOLERANCE = 0.01  # 1%


def parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def get_daily(spend: dict | None) -> dict | None:
    """The usable `daily` block, or None when it is absent or not usable (never fabricated)."""
    daily = (spend or {}).get("daily")
    if not isinstance(daily, dict):
        return None
    if not isinstance(daily.get("series"), list) or not isinstance(daily.get("dailyTotal"), list):
        return None
    if parse_date(daily.get("from")) is None or parse_date(daily.get("to")) is None:
        return None
    return daily


def window(daily: dict) -> tuple[date, date]:
    return parse_date(daily["from"]), parse_date(daily["to"])


def all_dates(daily: dict) -> list[date]:
    start, end = window(daily)
    if end < start:
        return []
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def provisional_from(daily: dict) -> date:
    """First provisional day: the recorded `provisionalFrom`, else the last PROVISIONAL_DAYS days."""
    recorded = parse_date(daily.get("provisionalFrom"))
    if recorded:
        return recorded
    _, end = window(daily)
    return end - timedelta(days=PROVISIONAL_DAYS - 1)


def settled_through(daily: dict) -> date:
    """Last day whose cost is considered settled."""
    return provisional_from(daily) - timedelta(days=1)


def total_by_date(daily: dict) -> dict[date, float]:
    """All-services cost per day (from `dailyTotal`); days with no row are zero."""
    out = {d: 0.0 for d in all_dates(daily)}
    for row in daily["dailyTotal"]:
        d = parse_date(row.get("date")) if isinstance(row, dict) else None
        if d is not None and isinstance(row.get("cost"), (int, float)):
            out[d] = out.get(d, 0.0) + float(row["cost"])
    return out


def series_by_service(daily: dict) -> dict[str, dict[date, float]]:
    """{service: {date: cost}} with every day of the window present (zero when no row)."""
    dates = all_dates(daily)
    out: dict[str, dict[date, float]] = {}
    for row in daily["series"]:
        if not isinstance(row, dict):
            continue
        d, svc, cost = parse_date(row.get("date")), row.get("service"), row.get("cost")
        if d is None or not isinstance(svc, str) or not isinstance(cost, (int, float)):
            continue
        out.setdefault(svc, {x: 0.0 for x in dates})
        out[svc][d] = out[svc].get(d, 0.0) + float(cost)
    return out


def service_order(daily: dict) -> list[str]:
    """Services by total cost over the window (largest first), with 'Other' always last."""
    by_service = series_by_service(daily)
    named = sorted(
        (s for s in by_service if s != OTHER), key=lambda s: sum(by_service[s].values()), reverse=True
    )
    return named + ([OTHER] if OTHER in by_service else [])


def aggregate_total(spend: dict) -> float | None:
    """The period total from the aggregates (totalLastMonth, else the sum of byService)."""
    if spend.get("totalLastMonth") is not None:
        return float(spend["totalLastMonth"])
    rows = spend.get("byService")
    if isinstance(rows, list) and rows and all(isinstance(r, dict) and "cost" in r for r in rows):
        return float(sum(r["cost"] for r in rows))
    return None


def reconcile(spend: dict, tolerance: float = RECONCILE_TOLERANCE) -> dict:
    """Compare the sum of the daily totals with the aggregate period total.

    Returns {"status": "ok" | "mismatch" | "skipped", "dailySum", "aggregateTotal", "deltaPct",
    "reason"}. It is skipped (never guessed) when there is no daily block or no aggregate, when
    the windows differ, or when the two sides are in different currencies.
    """
    daily = get_daily(spend)
    result = {"status": "skipped", "dailySum": None, "aggregateTotal": None, "deltaPct": None}
    if daily is None:
        return {**result, "reason": "no daily data"}
    aggregate = aggregate_total(spend)
    if aggregate is None:
        return {**result, "reason": "no aggregate total to compare with"}
    d_cur, s_cur = daily.get("currency"), spend.get("currency")
    if d_cur and s_cur and d_cur != s_cur:
        return {**result, "reason": f"currencies differ ({d_cur} vs {s_cur}); not compared"}
    for key in ("from", "to"):
        if spend.get(key) and daily.get(key) and spend[key] != daily[key]:
            return {**result, "reason": "daily and aggregate windows differ"}
    daily_sum = round(sum(total_by_date(daily).values()), 2)
    if aggregate == 0:
        delta = 0.0 if daily_sum == 0 else 1.0
    else:
        delta = abs(daily_sum - aggregate) / abs(aggregate)
    return {
        "status": "ok" if delta <= tolerance else "mismatch",
        "dailySum": daily_sum,
        "aggregateTotal": round(aggregate, 2),
        "deltaPct": round(delta * 100, 2),
        "reason": "",
    }
