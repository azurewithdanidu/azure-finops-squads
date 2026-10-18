"""Pure/IO helpers for the finops-squad dashboard, kept separate from scripts/dashboard.py so they
can be imported and unit-tested without triggering Streamlit's script-runner context.

Nothing in this module calls Streamlit, Azure, or mutates any artifact — it only reads
`.finops/runs/<id>/` files and shapes them into plain dicts / DataFrames.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

TIER_ORDER = ["T0", "T1", "T2", "T3"]
STATUS_ORDER = ["proposed", "approved", "pr-open", "merged", "verified", "rejected"]

# Confidence as text plus a small shape meter (never colour alone).
CONFIDENCE_LABELS = {"high": "▰▰▰ High", "medium": "▰▰▱ Medium", "low": "▰▱▱ Low"}


def confidence_label(value) -> str:
    return CONFIDENCE_LABELS.get(str(value).lower(), "—" if value in (None, "") else str(value))


def compact_number(value, decimals: int = 2) -> str:
    """Compact display for chart labels: 7.3 -> '7.30', 1234 -> '1.2K', 2_500_000 -> '2.5M'."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    sign = "-" if n < 0 else ""
    n = abs(n)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= limit:
            return f"{sign}{n / limit:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{sign}{n:.{decimals}f}"


_MD_SPECIALS = "\\`*_{}[]()#+-.!|<>~$&:"


def md_escape(text) -> str:
    """Neutralise Markdown/HTML-significant characters in untrusted artifact text so it renders
    literally (no links, images, emphasis or entities) when passed to st.markdown."""
    if text is None:
        return ""
    return "".join("\\" + ch if ch in _MD_SPECIALS else ch for ch in str(text)).replace("\n", " ")


def safe_url(url) -> str | None:
    """Only http(s) URLs may become clickable links; anything else from an artifact is dropped."""
    if isinstance(url, str) and url.strip().lower().startswith(("https://", "http://")):
        return url.strip()
    return None


def money_format(currency, per_row_currency: bool) -> str:
    """printf-style format for st.column_config.NumberColumn. The currency code comes from an
    artifact, so only a plain 3-letter code is allowed into the format string ('%' would break
    it). With mixed currencies the amount is bare and each row carries its own currency column."""
    code = str(currency or "")
    if per_row_currency or not (len(code) == 3 and code.isascii() and code.isalpha()):
        return "%.2f"
    return f"{code} %.2f"


def short_id(value, keep: int = 8) -> str:
    """Shorten a long identifier (e.g. a subscription GUID) for headers: '40668c14…'."""
    text = str(value or "—")
    return text if len(text) <= keep + 1 else text[:keep] + "…"


def is_approximate(kpi: dict | None) -> bool:
    """True when a KPI's method says it is an approximation (e.g. tagCoverageApproximate)."""
    return "approx" in str((kpi or {}).get("method", "")).lower()


def run_fingerprint(run: Path) -> tuple:
    """(relative path, mtime_ns, size) for every JSON file a run's dashboard view reads, so the
    cached loaders re-read only when something actually changed on disk."""
    items = []
    for sub in ("", "findings", "verification", "reports"):
        folder = run / sub if sub else run
        if folder.is_dir():
            for path in sorted(folder.glob("*.json")):
                st = path.stat()
                items.append((f"{sub}/{path.name}", st.st_mtime_ns, st.st_size))
    return tuple(items)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_runs(runs_dir: Path) -> list[Path]:
    if not runs_dir.is_dir():
        return []
    return sorted((p for p in runs_dir.iterdir() if p.is_dir()), reverse=True)


def load_findings(run: Path) -> list[dict]:
    findings: list[dict] = []
    fdir = run / "findings"
    if not fdir.is_dir():
        return findings
    for path in sorted(fdir.glob("*.json")):
        doc = load_json(path)
        if doc is None:
            continue
        items = doc if isinstance(doc, list) else doc.get("findings", [doc])
        for item in items:
            if isinstance(item, dict) and "id" in item:
                findings.append(item)
    return findings


def load_verifications(run: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    vdir = run / "verification"
    if not vdir.is_dir():
        return out
    for path in sorted(vdir.glob("*.json")):
        doc = load_json(path)
        if isinstance(doc, dict) and "findingId" in doc:
            out[doc["findingId"]] = doc
    return out


def load_iteration(run: Path) -> dict | None:
    """Load the structured iteration brief (iteration.json), if one was captured for this run.

    Returns None when the run has no iteration brief — iteration tracking is optional, and the
    dashboard must render exactly as before for any run that didn't use it.
    """
    return load_json(run / "iteration.json")


def load_kpis(run: Path) -> dict | None:
    """Load the named KPI set (reports/kpis.json), if `scripts/kpis.py` has been run for this run.

    Returns None when absent — KPIs are an additive reporting layer, not a hard requirement, so
    the dashboard must degrade gracefully (same pattern as load_iteration).
    """
    return load_json(run / "reports" / "kpis.json")


# The 5 trendable named KPIs and the dotted path to each one's numeric value, used by
# kpi_trend_dataframe. unitEconomics is deliberately excluded: its "method" (azure-openai-tokens
# vs manual-denominator) can change run-to-run, which would make a single trend line compare
# incompatible units -- it's shown as a headline card in dashboard.py instead, not trended.
KPI_VALUE_PATHS = {
    "taggingCompliance": ("kpis", "taggingCompliance", "value"),
    "allocationCoverage": ("kpis", "allocationCoverage", "value"),
    "estimatedSavingsOpportunity": ("kpis", "estimatedSavingsOpportunity", "value"),
    "realisedSavingsRate": ("kpis", "realisedSavingsRate", "value"),
    "anomalyCount": ("kpis", "anomalyCount", "value"),
}


def kpi_trend_dataframe(runs: list[Path], metric_key: str) -> pd.DataFrame:
    """Build a run-over-run trend for one named KPI across every run folder in `runs`.

    `runs` should be sorted oldest-first (reverse of dashboard.list_runs()'s newest-first order)
    so a line chart reads left-to-right chronologically. Runs with no kpis.json, or where this
    specific metric is unavailable, get `available=False` and `value=None` rather than being
    silently dropped — the caller can choose to show gaps instead of a misleadingly smooth line.
    """
    path = KPI_VALUE_PATHS.get(metric_key)
    if path is None:
        raise ValueError(f"Unknown KPI metric_key: {metric_key!r}")

    rows = []
    for run in runs:
        kpis = load_kpis(run)
        value = None
        if kpis is not None:
            node = kpis
            for key in path:
                if not isinstance(node, dict):
                    node = None
                    break
                node = node.get(key)
            value = node
        rows.append({"runId": run.name, "value": value, "available": value is not None})
    return pd.DataFrame(rows)


def compare_runs(findings_a: list[dict], findings_b: list[dict]) -> dict[str, list[dict]]:
    """Diff two runs' findings by (type, resourceId) — not by `id`, which is only stable within a
    single run's own numbering. Returns:
    - "resolved": present in `findings_a` (the earlier run) but not in `findings_b` (the later run)
    - "new": present in `findings_b` but not in `findings_a`
    - "recurring": present in both — i.e. still open since the earlier run
    Used to tell a repeat scan apart from real progress (see finops-reporting's retrospective).
    """

    def key(f: dict) -> tuple:
        return (f.get("type"), f.get("resourceId"))

    by_key_a = {key(f): f for f in findings_a}
    by_key_b = {key(f): f for f in findings_b}
    keys_a, keys_b = set(by_key_a), set(by_key_b)

    return {
        "resolved": [by_key_a[k] for k in sorted(keys_a - keys_b, key=str)],
        "new": [by_key_b[k] for k in sorted(keys_b - keys_a, key=str)],
        "recurring": [by_key_b[k] for k in sorted(keys_a & keys_b, key=str)],
    }


def findings_dataframe(findings: list[dict], verifs: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for f in findings:
        saving = f.get("estimatedMonthlySaving", {}) or {}
        iac = f.get("iacMatch", {}) or {}
        ver = verifs.get(f.get("id"))
        rows.append(
            {
                "id": f.get("id"),
                "type": f.get("type"),
                "tier": f.get("tier"),
                "estimatedMonthly": float(saving.get("amount", 0) or 0),
                "currency": saving.get("currency", "AUD"),
                "basis": saving.get("basis"),
                "confidence": f.get("confidence"),
                "effort": f.get("effort"),
                "iacMatch": iac.get("status"),
                "status": f.get("status"),
                "verifiedResult": (ver or {}).get("result"),
                "realisedMonthly": float((ver or {}).get("realisedSaving", 0) or 0)
                if ver and ver.get("result") in {"confirmed", "partial"}
                else 0.0,
                "resourceId": f.get("resourceId"),
                "summary": f.get("summary"),
                "prUrl": safe_url(f.get("prUrl")),
            }
        )
    return pd.DataFrame(rows)
