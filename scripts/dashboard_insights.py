"""Pure logic shared by the Executive and Engineering dashboard views.

Both views take their numbers from these functions (and from `dashboard_helpers`), so they cannot
disagree. Nothing here imports Streamlit, calls Azure, or mutates artifacts.

Money is always handled per currency: nothing in this module adds or compares amounts across
currencies, and estimated and realised amounts are never merged.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from dashboard_helpers import BUCKETS, classify_finding

CURRENCY_SYMBOLS = {"AUD": "A$", "NZD": "NZ$", "CAD": "C$", "GBP": "£", "EUR": "€"}

# Executive wording for the buckets (no jargon).
EXEC_BUCKET_LABELS = {
    "ready": "Ready to action",
    "blocked_iac": "Blocked on repo access",
    "decision": "Waiting on a decision",
    "in_flight": "In progress",
    "informational": "Informational / closed",
}

DEFAULT_REQUIRED_TAGS = ["owner", "environment", "application"]
ARTIFACTS = [
    ("Inventory", "inventory.json"),
    ("Spend", "spend.json"),
    ("Advisor", "advisor.json"),
    ("Findings", "findings/*.json"),
    ("KPIs", "reports/kpis.json"),
    ("Savings ledger", "reports/savings-ledger.json"),
    ("Verification", "verification/*.json"),
]


# ------------------------------------------------------------------------------- formatting
def money_text(currency, amount) -> str:
    """'A$149.81' for AUD (and a few other symbols), 'USD 6,812.63' otherwise."""
    code = str(currency or "").upper()
    if not (len(code) == 3 and code.isascii() and code.isalpha()):
        code = "?"
    value = f"{float(amount or 0):,.2f}"
    symbol = CURRENCY_SYMBOLS.get(code)
    return f"{symbol}{value}" if symbol else f"{code} {value}"


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def pretty_date(value) -> str:
    d = _parse_date(value)
    return f"{d.day} {d.strftime('%b %Y')}" if d else str(value or "—")


def lead_sentence(text, limit: int = 240) -> str:
    """The first sentence of a long summary, capped at `limit` characters."""
    clean = " ".join(str(text or "").split())
    cut = clean.find(". ")
    if 0 < cut < limit:
        return clean[: cut + 1]
    return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"


def confidence_words(value) -> str:
    return {"high": "High", "medium": "Medium", "low": "Low"}.get(str(value).lower(), "Not stated")


def portal_url(resource_id) -> str | None:
    """Azure Portal deep link for a full ARM resource id; None for anything else (e.g. the
    '(subscription-scope)' placeholder). The id is percent-encoded because it is untrusted."""
    rid = str(resource_id or "")
    if not rid.startswith("/subscriptions/"):
        return None
    return "https://portal.azure.com/#@/resource" + quote(rid, safe="/")


# ------------------------------------------------------------------------- savings and spend
def bucket_totals(df: pd.DataFrame) -> dict[str, dict[str, dict]]:
    """{currency: {bucket: {"amount": estimated monthly, "count": findings}}} -- one entry per
    currency, every bucket present. The single source for bucket amounts in both views."""
    out: dict[str, dict[str, dict]] = {}
    if df is None or df.empty:
        return out
    for currency, group in df.groupby("currency"):
        buckets = {b: {"amount": 0.0, "count": 0} for b in BUCKETS}
        for bucket, rows in group.groupby("bucket"):
            buckets[bucket] = {
                "amount": round(float(rows["estimatedMonthly"].sum()), 2),
                "count": int(len(rows)),
            }
        out[str(currency)] = buckets
    return out


def realised_by_currency(df: pd.DataFrame) -> dict[str, float]:
    if df is None or df.empty:
        return {}
    return {str(c): round(float(g["realisedMonthly"].sum()), 2) for c, g in df.groupby("currency")}


def estimated_total(buckets: dict[str, dict]) -> float:
    return round(sum(v["amount"] for v in buckets.values()), 2)


def spend_window(spend: dict) -> tuple[date | None, date | None, int | None]:
    start, end = _parse_date(spend.get("from")), _parse_date(spend.get("to"))
    days = (end - start).days + 1 if start and end and end >= start else None
    return start, end, days


def monthly_run_rate(total, days) -> float | None:
    """Average monthly spend over a window of `days` days (a month = 365/12 days)."""
    if total is None or not days:
        return None
    return float(total) / (days / (365 / 12))


def spend_total(spend: dict) -> float | None:
    if str(spend.get("status", "")).lower() == "unavailable":
        return None
    if spend.get("totalLastMonth") is not None:
        return float(spend["totalLastMonth"])
    rows = spend.get("byService")
    if isinstance(rows, list) and rows and all(isinstance(r, dict) and "cost" in r for r in rows):
        return float(sum(r["cost"] for r in rows))
    return None


def _savings_clause(currency: str, b: dict[str, dict]) -> str:
    parts = [
        f"{money_text(currency, b['ready']['amount'])} ready to action",
        f"{money_text(currency, b['blocked_iac']['amount'])} blocked on access to the "
        "infrastructure repo",
        f"{money_text(currency, b['decision']['amount'])} waiting on an owner decision",
    ]
    if b["in_flight"]["amount"] > 0:
        parts.append(f"{money_text(currency, b['in_flight']['amount'])} already in progress")
    if b["informational"]["amount"] > 0:
        parts.append(f"{money_text(currency, b['informational']['amount'])} informational or closed")
    return f"{money_text(currency, estimated_total(b))} a month of estimated savings: " + ", ".join(
        parts
    )


def build_headline(
    spend: dict,
    buckets: dict[str, dict[str, dict]],
    realised: dict[str, float],
    primary_currency: str,
) -> str:
    """Plain-English summary of spend and savings.

    Spend and savings are separate clauses (different currencies are never combined or put in a
    ratio). Each savings currency gets its own clause, primary currency first.
    """
    spend_sentence = "No spend breakdown was captured for this run."
    if str(spend.get("status", "")).lower() == "unavailable":
        spend_sentence = "Spend data is not available for this run."
    else:
        total = spend_total(spend)
        if total is not None:
            cur = spend.get("currency") or primary_currency
            _, end, days = spend_window(spend)
            if days and end:
                rate = monthly_run_rate(total, days)
                spend_sentence = (
                    f"Spend was {money_text(cur, total)} over the {days} days to "
                    f"{pretty_date(end)} (about {money_text(cur, rate)} a month)."
                )
            else:
                spend_sentence = f"Spend was {money_text(cur, total)} in the period captured."

    currencies = sorted(buckets, key=lambda c: (c != primary_currency, c))
    if not currencies:
        savings_sentence = "No findings yet, so no savings have been estimated."
        realised_sentence = f"Realised so far: {money_text(primary_currency, 0)}."
    else:
        clauses = []
        for c in currencies:
            if estimated_total(buckets[c]) > 0:
                clauses.append(_savings_clause(c, buckets[c]))
        if not clauses:
            savings_sentence = "We found issues, but none has an estimated saving yet."
        elif len(currencies) == 1:
            savings_sentence = "We found " + clauses[0] + "."
        else:
            savings_sentence = (
                "Savings are estimated in more than one currency, so they are listed "
                "separately and never added together: " + "; ".join(clauses) + "."
            )
        realised_sentence = "Realised so far: " + "; ".join(
            money_text(c, realised.get(c, 0.0)) for c in currencies
        ) + "."
    return " ".join([spend_sentence, savings_sentence, realised_sentence])


# ------------------------------------------------------------------------------- reliability
def reliability_notes(
    spend: dict,
    kpis: dict | None,
    config: dict,
    savings_currency: str,
    mixed_currencies: bool,
    kpi_labels: dict[str, str],
) -> list[str]:
    """Plain-language caveats for the 'How reliable are these numbers?' section."""
    notes = ["Savings are estimates. Nothing counts as realised until a change is merged and verified."]
    k = (kpis or {}).get("kpis", {})
    tc = k.get("taggingCompliance") or {}
    if "approx" in str(tc.get("method", "")).lower():
        notes.append(
            "Tag compliance is approximate: it is an upper bound worked out from the single "
            "worst-covered tag, so the true figure is probably lower."
        )
    start, end, _ = spend_window(spend)
    wanted = _parse_date((config.get("timeWindow") or {}).get("start"))
    if start and wanted and start > wanted:
        notes.append(
            f"The spend window was shortened to {pretty_date(start)} – {pretty_date(end)} because "
            f"Azure only allows cost queries a limited time back (we asked for {pretty_date(wanted)})."
        )
    spend_currency = spend.get("currency")
    if spend_currency and spend_currency != savings_currency and spend_total(spend) is not None:
        notes.append(
            f"Spend is in {spend_currency} (the subscription's billing currency) while savings "
            f"are estimated in {savings_currency}. The two are never converted or combined."
        )
    if mixed_currencies:
        notes.append(
            "Savings come in more than one currency. Each currency is shown on its own and "
            "never added to another."
        )
    unavailable = [
        f"{kpi_labels.get(name, name)}: {kpi.get('note', 'no reason recorded')}"
        for name, kpi in k.items()
        if isinstance(kpi, dict) and kpi.get("value") is None
    ]
    if kpis is None:
        notes.append("No KPI set was generated for this run, so KPI figures are unavailable.")
    for text in unavailable:
        notes.append(f"Not available this run — {text}")
    return notes


# -------------------------------------------------------------------------------- iteration
def goal_progress(goal: dict) -> float | None:
    """Fraction of the way from baseline to target (0..1), or None when it can't be computed."""
    try:
        base = float((goal.get("baseline") or {}).get("value"))
        target = float((goal.get("target") or {}).get("value"))
        current = float(((goal.get("current") or goal.get("baseline")) or {}).get("value"))
    except (TypeError, ValueError):
        return None
    if target == base:
        return 1.0 if current == target else 0.0
    return min(1.0, max(0.0, (current - base) / (target - base)))


def goal_value_text(point: dict | None) -> str:
    point = point or {}
    value = point.get("value")
    if value is None:
        return "—"
    if point.get("currency"):
        return money_text(point["currency"], value)
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


# --------------------------------------------------------------------------- engineering
def blocker_and_next_step(finding: dict, bucket: str | None = None) -> tuple[str, str]:
    """Rule-based (what blocks this, next step) pair for a finding's bucket."""
    bucket = bucket or classify_finding(finding)
    tier = finding.get("tier")
    iac = (finding.get("iacMatch") or {}).get("status")
    if bucket == "ready":
        return (
            "Nothing — IaC was matched and the tier allows a change.",
            "Ask the Implementer to open a PR"
            + (" (a draft PR, after explicit confirmation)." if tier == "T2" else "."),
        )
    if bucket == "blocked_iac":
        if iac == "unmanaged":
            return (
                "The resource is not managed by IaC.",
                "The Implementer will produce a manual change request instead of a PR.",
            )
        return (
            "No IaC match was found — the IaC repo is not available to this workspace, or the "
            "resource isn't in it.",
            "Add the IaC repo to the workspace and re-run iac-matching.",
        )
    if bucket == "decision":
        if tier == "T3":
            return (
                "Tier T3: this needs an owner decision and the Implementer will not act on it.",
                "Get the resource owner to confirm intent, then decide on the change manually.",
            )
        return (
            "No risk tier is recorded, and the Implementer refuses untiered findings.",
            "Re-run risk-tier-assessment to assign a tier.",
        )
    if bucket == "in_flight":
        return (
            f"A change is already underway (status: {finding.get('status')}).",
            "Review or merge the PR, then run verification to confirm the saving.",
        )
    return (
        "Nothing — informational or already closed.",
        "No action required.",
    )


def tag_coverage_rows(inventory: dict | None, required: list[str]) -> list[dict]:
    """Per required tag: resources missing it and coverage %, from inventory.tagCoverage."""
    cov = (inventory or {}).get("tagCoverage")
    if not isinstance(cov, dict) or not cov.get("total"):
        return []
    total = cov["total"]
    lowered = {str(k).lower(): v for k, v in cov.items()}
    rows = []
    for tag in required:
        missing = lowered.get("missing" + str(tag).lower())
        if missing is None:
            continue
        rows.append(
            {
                "tag": str(tag),
                "missing": int(missing),
                "total": int(total),
                "coverage": round(100.0 * (total - missing) / total, 1),
            }
        )
    return rows


def required_tags(kpis: dict | None, config: dict) -> list[str]:
    from_kpis = (kpis or {}).get("requiredTags")
    if isinstance(from_kpis, list) and from_kpis:
        return [str(t) for t in from_kpis]
    from_config = (config.get("tagging") or {}).get("requiredTags")
    if isinstance(from_config, list) and from_config:
        return [str(t) for t in from_config]
    return list(DEFAULT_REQUIRED_TAGS)


def artifact_checklist(run: Path) -> dict[str, bool]:
    """Which expected artifacts exist for a run folder."""
    out = {}
    for label, pattern in ARTIFACTS:
        out[label] = bool(list(run.glob(pattern))) if "*" in pattern else (run / pattern).is_file()
    return out


def read_text_file(path: Path, limit: int = 200_000) -> str | None:
    """Read a Markdown artifact (size-capped); None if absent or unreadable."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return None


def window_label(start: date | None, end: date | None) -> str:
    return f"{pretty_date(start)} to {pretty_date(end)}" if start and end else "—"

