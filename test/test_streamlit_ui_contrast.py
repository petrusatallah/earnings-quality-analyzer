import re
from pathlib import Path


APP_SOURCE = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")


def _css_rule(selector_fragment: str) -> str:
    match = re.search(
        rf"{re.escape(selector_fragment)}[^{{]*\{{(?P<body>.*?)\}}",
        APP_SOURCE,
        flags=re.DOTALL,
    )
    assert match is not None, f"Missing CSS selector: {selector_fragment}"
    return match.group("body")


def test_light_streamlit_controls_have_explicit_dark_text_colors() -> None:
    expected_colors = {
        '.stTabs [data-baseweb="tab"] p': "#5c697b",
        '.stButton > button[kind="secondary"] p': "#294562",
        '[data-baseweb="select"] span': "#27364b",
        '[data-testid="stNumberInputContainer"] input': "#27364b",
        '[data-testid="stExpander"] summary *': "#344d69",
        '[data-testid="stAlert"] p': "#34465d",
        '[data-testid="stCaptionContainer"] p': "#657286",
        '[data-testid="stDataFrame"] [role="columnheader"] *': "#233b58",
    }

    for selector, color in expected_colors.items():
        assert f"color: {color}" in _css_rule(selector)


def test_dark_controls_keep_explicit_white_text() -> None:
    dark_surface_selectors = (
        '> button[data-baseweb="tab"][aria-selected="true"] p',
        '.stButton > button[kind="primary"] p',
        '[data-testid="stDownloadButton"] > button p',
    )

    for selector in dark_surface_selectors:
        assert "color: #ffffff" in _css_rule(selector)


def test_help_text_inherits_the_tooltip_surface_contrast() -> None:
    assert "color: inherit" in _css_rule('[data-testid="stTooltipContent"] p')
    assert "color: inherit" in _css_rule('[data-testid="stTooltipErrorContent"] p')
