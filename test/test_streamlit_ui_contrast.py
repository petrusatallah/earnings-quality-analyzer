import re
import tomllib
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]
APP_SOURCE = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
THEME_CONFIG = tomllib.loads(
    (PROJECT_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
)


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
        '.stTabs [data-baseweb="tab"] span': "#5c697b",
        '.stTabs [aria-selected="true"] p': "var(--dashboard-navy)",
        '.stTabs [aria-selected="true"] span': "var(--dashboard-navy)",
        '.stButton > button[kind="secondary"] p': "#294562",
        '[data-baseweb="select"] span': "#27364b",
        '[data-testid="stNumberInputContainer"] input': "#27364b",
        '[data-testid="stProgress"] [data-testid="stMarkdownContainer"] p': "#34465d",
        '[data-testid="stProgress"] [data-testid="stMarkdownContainer"] span': "#34465d",
        '[data-testid="stExpander"] summary *': "#344d69",
        '[data-testid="stAlert"] p': "#34465d",
        '[data-testid="stCaptionContainer"] p': "#657286",
        '[data-testid="stDataFrame"] [role="columnheader"] *': "#233b58",
    }

    for selector, color in expected_colors.items():
        assert f"color: {color}" in _css_rule(selector)

    number_input_rule = _css_rule('[data-testid="stNumberInputContainer"] input')
    assert "-webkit-text-fill-color: #27364b" in number_input_rule


def test_analysis_navigation_labels_have_explicit_state_colors() -> None:
    states = {
        '> button[data-baseweb="tab"] p': "#5c697b",
        '> button[data-baseweb="tab"] span': "#5c697b",
        '> button[data-baseweb="tab"]:hover p': "var(--dashboard-navy)",
        '> button[data-baseweb="tab"]:hover span': "var(--dashboard-navy)",
        '> button[data-baseweb="tab"][aria-selected="true"] p': "#ffffff",
        '> button[data-baseweb="tab"][aria-selected="true"] span': "#ffffff",
    }

    for selector, color in states.items():
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


def test_streamlit_theme_is_consistently_light() -> None:
    required_theme = {
        "base": "light",
        "backgroundColor": "#f3f5f8",
        "secondaryBackgroundColor": "#ffffff",
        "textColor": "#182b49",
    }

    for setting, value in required_theme.items():
        assert THEME_CONFIG["theme"][setting] == value


def test_no_broad_global_text_override_is_present() -> None:
    stylesheet = APP_SOURCE.split("<style>", 1)[1].split("</style>", 1)[0]
    forbidden_selectors = (r"\.stApp\s+\*", r"^\s*p\s*\{", r"^\s*span\s*\{", r"button\s+\*")

    for selector in forbidden_selectors:
        assert re.search(selector, stylesheet, flags=re.MULTILINE) is None
