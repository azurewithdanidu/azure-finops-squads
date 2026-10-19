"""Design tokens for the finops-squad dashboard: one palette, one set of chart constants, and an
Altair theme built from them.

Pure data plus an Altair theme registration -- no Streamlit import, so it is unit-testable. The
Streamlit theme itself lives in `.streamlit/config.toml`; the categorical palette there must
match CATEGORICAL below.

Text, gridline and background colours are deliberately NOT set in the Altair theme: Streamlit
injects its own light/dark theme into every chart, and leaving those unset keeps charts readable
in both modes.
"""
from __future__ import annotations

import altair as alt

# Colour-blind-safe categorical palette (Okabe-Ito).
CATEGORICAL = [
    "#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#7A7A7A",
]
ACCENT = CATEGORICAL[0]

# Stacked/line series for the daily spend charts: top 10 services plus a fixed grey "Other".
SERIES_PALETTE = CATEGORICAL[:6] + ["#882255", "#44AA99", "#117733", "#332288"]
OTHER_COLOR = "#9aa0a6"

# Semantic colours. Estimated is muted grey on purpose: estimates are never counted as realised.
ESTIMATED = "#8b95a1"
REALISED = "#2e9e5b"
WARNING = "#E69F00"
DANGER = "#D55E00"

# Risk tiers. Always shown as text + colour (see TIER_LABELS), never colour alone.
TIER_COLORS = {"T0": "#34a853", "T1": "#4285f4", "T2": "#f9ab00", "T3": "#ea4335"}
TIER_LABELS = {"T0": "T0 · Safe", "T1": "T1 · Low", "T2": "T2 · Medium", "T3": "T3 · High"}

# Label colour for text marks (Vega's default is black, unreadable on dark backgrounds).
TEXT_COLORS = {"light": "#1b1f24", "dark": "#e6e9ee"}
MUTED_OPACITY = 0.45  # bars that are not the emphasised top item

# Spacing and chart sizing.
CHART_HEIGHT = 300
BAR_WIDTH = 64  # vertical bars; stops a single bar stretching across the card
BAR_ROW_HEIGHT = 26  # per-bar height for horizontal bar charts; keeps long lists readable
TREND_HEIGHT = CHART_HEIGHT
SPARKLINE_HEIGHT = 48
LABEL_FONT_SIZE = 12
TITLE_FONT_SIZE = 12
KPI_PER_ROW = 3
GRID_OPACITY = 0.25
TAGGING_TARGET = 90.0  # FinOps Framework tagging-compliance target (percent)


def _altair_theme() -> dict:
    return {
        "config": {
            "view": {"stroke": None, "continuousHeight": CHART_HEIGHT},
            "range": {"category": CATEGORICAL},
            "axis": {
                "labelFontSize": LABEL_FONT_SIZE,
                "titleFontSize": TITLE_FONT_SIZE,
                "titleFontWeight": "normal",
                "grid": True,
                "gridOpacity": GRID_OPACITY,
                "domain": False,
                "ticks": False,
            },
            "axisX": {"grid": False},
            "legend": {"labelFontSize": LABEL_FONT_SIZE, "titleFontSize": TITLE_FONT_SIZE},
            "bar": {"cornerRadiusEnd": 4},
            "line": {"strokeWidth": 2.5},
            "point": {"filled": True, "size": 60},
        }
    }


def register_altair_theme(name: str = "finops") -> None:
    """Register and enable the dashboard's Altair theme (idempotent)."""
    if hasattr(alt, "theme"):  # Altair >= 5.5
        alt.theme.register(name, enable=True)(lambda: alt.theme.ThemeConfig(_altair_theme()))
    else:  # older Altair
        alt.themes.register(name, _altair_theme)
        alt.themes.enable(name)
