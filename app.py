"""Streamlit application for the Task 109 production pipeline."""

import traceback
from html import escape
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

import altair as alt
import pandas as pd
import streamlit as st

from Data.manual_corrections import (
    create_manual_correction,
    effective_value,
    revert_manual_correction,
)
from main import (
    PIPELINE_STAGES,
    PipelineResult,
    PipelineStageError,
    available_fiscal_years,
    downloadable_workbook_path,
    pipeline_result_matches_selection,
    run_pipeline,
    sec_company_options,
)


st.set_page_config(
    page_title="Earnings Quality Analyzer",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root {
            --dashboard-navy: #182b49;
            --dashboard-bg: #f3f5f8;
            --dashboard-border: #dfe5ec;
            --dashboard-shadow: 0 4px 16px rgba(24, 43, 73, 0.07);
            --dashboard-radius: 12px;
            --dashboard-muted: #667386;
        }
        .stApp { background: var(--dashboard-bg); }
        header[data-testid="stHeader"] { background: transparent; }
        .block-container {
            max-width: 1480px;
            padding: 1.15rem 1.5rem 2rem;
        }
        .block-container h1, .block-container h2, .block-container h3 {
            color: var(--dashboard-navy);
            letter-spacing: -0.02em;
        }
        .block-container h1 { margin-bottom: 0.25rem; }
        .dashboard-header {
            padding: 0.35rem 0 1.15rem;
            border-bottom: 1px solid #dfe5ec;
            margin-bottom: 1.15rem;
        }
        .dashboard-eyebrow {
            color: #3f6f9c;
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            margin-bottom: 0.42rem;
        }
        .dashboard-title {
            color: var(--dashboard-navy);
            font-size: clamp(2rem, 3vw, 2.75rem);
            font-weight: 820;
            letter-spacing: -0.045em;
            line-height: 1.08;
            margin: 0;
        }
        .dashboard-header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-top: 0.7rem;
        }
        .dashboard-subtitle {
            color: var(--dashboard-muted);
            font-size: 0.86rem;
            line-height: 1.5;
            margin: 0;
        }
        .dashboard-scope {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            flex: 0 0 auto;
            color: #344d69;
            background: #eaf1f8;
            border: 1px solid #d5e1ed;
            border-radius: 999px;
            padding: 0.42rem 0.72rem;
            font-size: 0.72rem;
            font-weight: 700;
            white-space: nowrap;
        }
        .dashboard-scope-dot {
            width: 0.42rem;
            height: 0.42rem;
            border-radius: 50%;
            background: #3d79ad;
            box-shadow: 0 0 0 3px rgba(61, 121, 173, 0.12);
        }
        [data-testid="stSidebar"] {
            min-width: 280px !important;
            max-width: 280px !important;
            background: #fbfcfe;
            border-right: 1px solid #dce3eb;
            box-shadow: 4px 0 18px rgba(24, 43, 73, 0.055);
        }
        [data-testid="stSidebar"] > div:first-child {
            width: 280px !important;
            padding: 1.35rem 1rem;
        }
        .sidebar-brand {
            padding: 0.25rem 0.25rem 1.15rem;
            border-bottom: 1px solid #e1e6ed;
            margin-bottom: 1.1rem;
        }
        .sidebar-brand-title {
            color: var(--dashboard-navy);
            font-size: 1.55rem;
            font-weight: 800;
            line-height: 1.1;
            letter-spacing: -0.035em;
        }
        .sidebar-brand-subtitle {
            color: var(--dashboard-muted);
            font-size: 0.78rem;
            line-height: 1.45;
            margin-top: 0.6rem;
        }
        .sidebar-label {
            color: #8a95a5;
            font-size: 0.67rem;
            font-weight: 750;
            letter-spacing: 0.09em;
            text-transform: uppercase;
            margin: 0 0.2rem 0.6rem;
        }
        .sidebar-feature {
            display: flex;
            align-items: flex-start;
            gap: 0.65rem;
            padding: 0.72rem 0.68rem;
            margin-bottom: 0.5rem;
            background: #ffffff;
            border: 1px solid #e6ebf1;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(24, 43, 73, 0.035);
        }
        .sidebar-feature-icon {
            width: 38px;
            height: 38px;
            min-width: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 9px;
            background: #e8f2ff;
            color: #245d93;
            font-size: 0.7rem;
            font-weight: 800;
        }
        .sidebar-feature-title {
            color: #27364b;
            font-size: 0.8rem;
            font-weight: 750;
            line-height: 1.25;
        }
        .sidebar-feature-copy {
            color: #778295;
            font-size: 0.69rem;
            line-height: 1.4;
            margin-top: 0.18rem;
        }
        [data-testid="stMetric"] {
            min-height: 112px;
            background: linear-gradient(145deg, #ffffff 0%, #fbfcfe 100%);
            border: 1px solid var(--dashboard-border);
            border-radius: var(--dashboard-radius);
            box-shadow: var(--dashboard-shadow);
            padding: 0.85rem 0.95rem;
        }
        [data-testid="stMetricLabel"] {
            color: #6d798a;
            font-weight: 650;
        }
        [data-testid="stMetricValue"] {
            color: var(--dashboard-navy);
            font-weight: 780;
        }
        .analysis-banner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            background: linear-gradient(110deg, #182b49 0%, #244d78 100%);
            color: #ffffff;
            border-radius: 12px;
            padding: 0.9rem 1.1rem;
            margin: 0.2rem 0 0.9rem;
            box-shadow: 0 5px 18px rgba(24, 43, 73, 0.13);
        }
        .analysis-banner-title { font-size: 1rem; font-weight: 760; }
        .analysis-banner-copy { color: #d9e6f3; font-size: 0.76rem; margin-top: 0.2rem; }
        .analysis-banner-status {
            white-space: nowrap;
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.22);
            border-radius: 999px;
            padding: 0.38rem 0.68rem;
            font-size: 0.72rem;
            font-weight: 700;
        }
        .section-heading {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.1rem 0 0.85rem;
            padding-bottom: 0.72rem;
            border-bottom: 1px solid #e4e9ef;
        }
        .section-heading-title {
            color: var(--dashboard-navy);
            font-size: 1.2rem;
            font-weight: 780;
            letter-spacing: -0.02em;
        }
        .section-heading-copy {
            color: var(--dashboard-muted);
            font-size: 0.78rem;
            line-height: 1.5;
            margin-top: 0.24rem;
            max-width: 780px;
        }
        .section-summary {
            color: #536276;
            background: #f5f8fb;
            border-left: 4px solid #3f77a8;
            border-radius: 7px;
            padding: 0.62rem 0.78rem;
            margin: 0.2rem 0 0.85rem;
            font-size: 0.78rem;
            line-height: 1.45;
        }
        .section-status-heading {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            margin: 0.05rem 0 0.55rem;
        }
        .section-status-title {
            color: var(--dashboard-navy);
            font-size: 0.84rem;
            font-weight: 770;
            letter-spacing: -0.01em;
        }
        .section-status-period {
            color: #748195;
            font-size: 0.69rem;
            font-weight: 650;
        }
        .section-status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 0.65rem;
            margin: 0 0 0.8rem;
        }
        .section-status-card {
            min-width: 0;
            min-height: 88px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            background: #ffffff;
            border: 1px solid #dfe5ec;
            border-left: 4px solid #3f6f9c;
            border-radius: 10px;
            box-shadow: 0 3px 11px rgba(24, 43, 73, 0.05);
            padding: 0.72rem 0.8rem;
        }
        .section-status-label {
            color: #6b788a;
            font-size: 0.65rem;
            font-weight: 750;
            letter-spacing: 0.055em;
            line-height: 1.3;
            text-transform: uppercase;
            margin-bottom: 0.3rem;
        }
        .section-status-value {
            color: var(--dashboard-navy);
            font-size: 0.96rem;
            font-weight: 770;
            line-height: 1.3;
            overflow-wrap: anywhere;
        }
        .section-status-card.status-tone-concern {
            background: #fff8f8;
            border-color: #f0cbd0;
            border-left-color: #b53b48;
        }
        .section-status-card.status-tone-concern .section-status-value { color: #8f2530; }
        .section-status-card.status-tone-review {
            background: #fffaf0;
            border-color: #efdfad;
            border-left-color: #c39116;
        }
        .section-status-card.status-tone-review .section-status-value { color: #765600; }
        .section-status-card.status-tone-clear {
            background: #f5fbf7;
            border-color: #cfe5d5;
            border-left-color: #3f8a55;
        }
        .section-status-card.status-tone-clear .section-status-value { color: #276738; }
        .section-status-card.status-tone-unavailable {
            background: #f1f3f6;
            border-color: #cfd6df;
            border-left-color: #7b8796;
            box-shadow: none;
        }
        .section-status-card.status-tone-unavailable .section-status-value { color: #596778; }
        .analysis-content-label {
            color: var(--dashboard-navy);
            font-size: 0.83rem;
            font-weight: 760;
            letter-spacing: -0.01em;
            border-bottom: 1px solid #e3e8ee;
            padding-bottom: 0.48rem;
            margin: 1.05rem 0 0.7rem;
        }
        .investor-table-caption {
            color: #758296;
            font-size: 0.7rem;
            line-height: 1.45;
            margin: -0.32rem 0 0.55rem;
        }
        .correction-shell {
            background: linear-gradient(145deg, #f7fafe 0%, #ffffff 100%);
            border: 1px solid #dfe6ee;
            border-radius: 11px;
            padding: 0.85rem 0.95rem;
            margin: 0.45rem 0 0.8rem;
        }
        .correction-context {
            background: #ffffff;
            border: 1px solid #e3e8ef;
            border-radius: 9px;
            padding: 0.7rem 0.8rem;
            color: #536276;
            font-size: 0.75rem;
            line-height: 1.55;
            margin: 0.35rem 0 0.7rem;
        }
        .audit-heading {
            color: var(--dashboard-navy);
            font-size: 0.9rem;
            font-weight: 740;
            margin: 1rem 0 0.2rem;
        }
        .conclusion-card {
            position: relative;
            overflow: hidden;
            border: 1px solid #244767;
            border-radius: 14px;
            background: linear-gradient(120deg, #182b49 0%, #28547e 100%);
            padding: 1.25rem 1.3rem;
            margin: 0.15rem 0 1rem;
            box-shadow: 0 7px 22px rgba(24, 43, 73, 0.18);
        }
        .conclusion-card::after {
            content: "";
            position: absolute;
            width: 190px;
            height: 190px;
            right: -80px;
            top: -105px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.06);
        }
        .conclusion-label, .interpretation-label {
            color: #7a8798;
            font-size: 0.67rem;
            font-weight: 760;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .conclusion-card .conclusion-label { color: #bfcfe0; }
        .conclusion-title {
            position: relative;
            z-index: 1;
            color: #ffffff;
            font-size: clamp(1.45rem, 2.2vw, 1.95rem);
            font-weight: 820;
            letter-spacing: -0.03em;
            line-height: 1.2;
            margin: 0.25rem 0 0.45rem;
        }
        .conclusion-copy, .interpretation-copy {
            color: #4f5f73;
            font-size: 0.8rem;
            line-height: 1.55;
        }
        .conclusion-card .conclusion-copy {
            position: relative;
            z-index: 1;
            max-width: 980px;
            color: #e0eaf4;
            font-size: 0.84rem;
        }
        .conclusion-card .status-badge { position: relative; z-index: 1; }
        .interpretation-card {
            min-height: 100%;
            border: 1px solid #e0e6ed;
            border-radius: 12px;
            background: #ffffff;
            padding: 1rem 1.05rem;
            margin-bottom: 0.9rem;
            box-shadow: 0 4px 14px rgba(24, 43, 73, 0.06);
        }
        .interpretation-card-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.65rem;
            padding-bottom: 0.7rem;
            border-bottom: 1px solid #e6eaf0;
            margin-bottom: 0.75rem;
        }
        .interpretation-title {
            color: var(--dashboard-navy);
            font-size: 1.08rem;
            font-weight: 780;
            line-height: 1.3;
            margin: 0.16rem 0 0;
        }
        .status-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.25rem 0.52rem;
            margin: 0.15rem 0.2rem 0.45rem 0;
            font-size: 0.68rem;
            font-weight: 740;
        }
        .status-concern { background: #fdecee; color: #8f2530; }
        .status-review { background: #fff2cc; color: #765600; }
        .status-clear { background: #e7f5eb; color: #276738; }
        .status-unavailable { background: #eef1f5; color: #596778; }
        .interpretation-section {
            border: 1px solid #e5e9ef;
            border-radius: 9px;
            background: #fafbfd;
            padding: 0.68rem 0.74rem;
            margin-top: 0.58rem;
        }
        .interpretation-section.concerns { border-left: 4px solid #b53b48; }
        .interpretation-section.positives { border-left: 4px solid #3f8a55; }
        .interpretation-section.unavailable {
            border-left: 4px solid #7b8796;
            background: #f3f5f7;
        }
        .interpretation-section.assessment { border-left: 4px solid #3f6f9c; }
        .interpretation-section .interpretation-label { margin-bottom: 0.34rem; }
        .signal-list {
            margin: 0.45rem 0 0;
            padding-left: 1.05rem;
            color: #536276;
            font-size: 0.75rem;
            line-height: 1.5;
        }
        .signal-list li { margin-bottom: 0.28rem; }
        .investor-note {
            color: #606f82;
            background: #f4f6f9;
            border: 1px solid #e1e6ec;
            border-radius: 8px;
            padding: 0.65rem 0.75rem;
            margin: 0.15rem 0 0.9rem;
            font-size: 0.74rem;
            line-height: 1.5;
        }
        .red-flag-summary {
            display: grid;
            grid-template-columns: 1.4fr repeat(2, minmax(0, 1fr));
            gap: 0.7rem;
            margin: 0.1rem 0 0.8rem;
        }
        .red-flag-summary-card {
            min-width: 0;
            background: #ffffff;
            border: 1px solid #dfe5ec;
            border-radius: 11px;
            box-shadow: 0 3px 12px rgba(24, 43, 73, 0.055);
            padding: 0.82rem 0.9rem;
        }
        .red-flag-summary-card.status-tone-concern { border-left: 4px solid #b53b48; background: #fff8f8; }
        .red-flag-summary-card.status-tone-review { border-left: 4px solid #c39116; background: #fffaf0; }
        .red-flag-summary-card.status-tone-clear { border-left: 4px solid #3f8a55; background: #f5fbf7; }
        .red-flag-summary-card.status-tone-unavailable { border-left: 4px solid #7b8796; background: #f1f3f6; }
        .red-flag-summary-label {
            color: #6c798b;
            font-size: 0.65rem;
            font-weight: 750;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.28rem;
        }
        .red-flag-summary-value {
            color: var(--dashboard-navy);
            font-size: 1.12rem;
            font-weight: 790;
            line-height: 1.25;
        }
        .severity-legend {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.45rem;
            margin: 0.1rem 0 0.85rem;
        }
        .severity-legend-label {
            color: #6b788a;
            font-size: 0.69rem;
            font-weight: 700;
            margin-right: 0.1rem;
        }
        .severity-chip {
            border-radius: 999px;
            border: 1px solid transparent;
            padding: 0.3rem 0.58rem;
            font-size: 0.68rem;
            font-weight: 740;
        }
        .severity-chip.low { color: #276738; background: #e7f5eb; border-color: #c9e3d0; }
        .severity-chip.investigation { color: #765600; background: #fff2cc; border-color: #ecd999; }
        .severity-chip.concern { color: #8f2530; background: #fdecee; border-color: #efc9ce; }
        .severity-chip.unavailable { color: #596778; background: #eef1f5; border-color: #d2d8e0; }
        .red-flag-table-heading {
            color: var(--dashboard-navy);
            font-size: 0.84rem;
            font-weight: 760;
            border-bottom: 1px solid #e3e8ee;
            padding-bottom: 0.48rem;
            margin: 0.35rem 0 0.65rem;
        }
        .chart-caption {
            color: #788497;
            font-size: 0.7rem;
            margin: -0.2rem 0 0.35rem;
        }
        [data-testid="stDataFrame"],
        [data-testid="stVegaLiteChart"],
        [data-testid="stArrowVegaLiteChart"] {
            background: #ffffff;
            border: 1px solid var(--dashboard-border);
            border-radius: var(--dashboard-radius);
            box-shadow: var(--dashboard-shadow);
            overflow: hidden;
        }
        [data-testid="stDataFrame"] [role="columnheader"] {
            background: #edf3f8;
            color: #233b58;
            font-weight: 730;
        }
        [data-testid="stDataFrame"] [role="columnheader"] * { color: #233b58; }
        [data-testid="stDataFrame"] { margin-bottom: 0.25rem; }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem;
            padding: 0.32rem;
            background: #ffffff;
            border: 1px solid var(--dashboard-border);
            border-radius: var(--dashboard-radius);
            box-shadow: var(--dashboard-shadow);
        }
        .stTabs [data-baseweb="tab-panel"] {
            background: #ffffff;
            border: 1px solid var(--dashboard-border);
            border-radius: var(--dashboard-radius);
            box-shadow: var(--dashboard-shadow);
            margin-top: 0.55rem;
            padding: 1rem 1.05rem 1.15rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            padding-left: 0.82rem;
            padding-right: 0.82rem;
            color: #5c697b;
        }
        .stTabs [data-baseweb="tab"] p,
        .stTabs [data-baseweb="tab"] span { color: #5c697b; }
        .stTabs [aria-selected="true"] {
            background: #eaf1f8;
            color: var(--dashboard-navy);
            font-weight: 700;
        }
        .stTabs [aria-selected="true"] p,
        .stTabs [aria-selected="true"] span { color: var(--dashboard-navy); }
        .st-key-analysis_navigation > div[data-baseweb="tab-list"] {
            gap: 0.2rem;
            padding: 0.4rem;
            background: #ffffff;
            border: 1px solid #dbe3ec;
            border-radius: 13px;
            box-shadow: 0 4px 14px rgba(24, 43, 73, 0.055);
            overflow-x: auto;
            scrollbar-width: thin;
        }
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"] {
            min-height: 2.55rem;
            padding: 0.52rem 0.76rem;
            border-radius: 9px;
            color: #5c697b;
            font-size: 0.76rem;
            font-weight: 650;
            line-height: 1.2;
            white-space: nowrap;
        }
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"] p,
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"] span { color: #5c697b; }
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"]:hover {
            color: var(--dashboard-navy);
            background: #f0f4f8;
        }
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"]:hover p,
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"]:hover span { color: var(--dashboard-navy); }
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"][aria-selected="true"] {
            color: #ffffff;
            background: linear-gradient(110deg, #182b49 0%, #28547e 100%);
            box-shadow: 0 3px 9px rgba(24, 43, 73, 0.18);
            font-weight: 750;
        }
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"][aria-selected="true"] p,
        .st-key-analysis_navigation > div[data-baseweb="tab-list"]
        > button[data-baseweb="tab"][aria-selected="true"] span { color: #ffffff; }
        .st-key-analysis_navigation > div[data-baseweb="tab-panel"] {
            background: transparent;
            border: 0;
            border-radius: 0;
            box-shadow: none;
            margin-top: 0.65rem;
            padding: 0.85rem 0 1rem;
        }
        .overview-summary {
            display: grid;
            grid-template-columns: minmax(1.35fr, 2fr) repeat(3, minmax(0, 1fr));
            gap: 0;
            background: linear-gradient(120deg, #182b49 0%, #244d78 100%);
            border: 1px solid #244767;
            border-radius: 13px;
            box-shadow: 0 6px 18px rgba(24, 43, 73, 0.14);
            overflow: hidden;
            margin: 0.1rem 0 1.15rem;
        }
        .overview-summary-item {
            min-width: 0;
            padding: 0.9rem 1rem;
            border-left: 1px solid rgba(255, 255, 255, 0.13);
        }
        .overview-summary-item:first-child { border-left: 0; }
        .overview-summary-label {
            color: #bfcfe0;
            font-size: 0.65rem;
            font-weight: 760;
            letter-spacing: 0.075em;
            text-transform: uppercase;
            margin-bottom: 0.32rem;
        }
        .overview-summary-value {
            color: #ffffff;
            font-size: 0.88rem;
            font-weight: 740;
            line-height: 1.35;
            overflow-wrap: anywhere;
        }
        .overview-section-label {
            color: var(--dashboard-navy);
            font-size: 0.83rem;
            font-weight: 760;
            letter-spacing: -0.01em;
            margin: 0.15rem 0 0.6rem;
        }
        .st-key-analysis_overview [data-testid="stMetric"] {
            min-height: 124px;
            padding: 0.95rem 1rem;
            border-color: #dce4ed;
            border-top: 3px solid #315f8a;
            box-shadow: 0 4px 14px rgba(24, 43, 73, 0.06);
        }
        .st-key-analysis_overview [data-testid="stMetricLabel"] {
            min-height: 2.2rem;
            align-items: flex-start;
            color: #657286;
            font-size: 0.74rem;
            font-weight: 690;
            line-height: 1.25;
        }
        .st-key-analysis_overview [data-testid="stMetricValue"] {
            color: var(--dashboard-navy);
            font-size: clamp(1.25rem, 1.7vw, 1.7rem);
            line-height: 1.2;
        }
        .st-key-analysis_overview [data-testid="stVegaLiteChart"],
        .st-key-analysis_overview [data-testid="stArrowVegaLiteChart"] {
            margin-bottom: 0.35rem;
        }
        .stButton > button, [data-testid="stDownloadButton"] > button {
            min-height: 2.6rem;
            border-radius: 9px;
            font-size: 0.78rem;
            font-weight: 700;
            transition: border-color 150ms ease, background 150ms ease, box-shadow 150ms ease;
        }
        .stButton > button[kind="secondary"] {
            color: #294562;
            background: #ffffff;
            border-color: #cfd9e4;
        }
        .stButton > button[kind="secondary"] p { color: #294562; }
        .stButton > button[kind="secondary"]:hover {
            color: var(--dashboard-navy);
            border-color: #8fa6bc;
            background: #f7f9fb;
        }
        .stButton > button[kind="secondary"]:hover p { color: var(--dashboard-navy); }
        [data-testid="stDownloadButton"] > button {
            color: #ffffff;
            background: linear-gradient(110deg, #182b49 0%, #28547e 100%);
            border: 1px solid #182b49;
            box-shadow: 0 4px 12px rgba(24, 43, 73, 0.16);
        }
        [data-testid="stDownloadButton"] > button p { color: #ffffff; }
        [data-testid="stDownloadButton"] > button:hover {
            color: #ffffff;
            border-color: #244d78;
            background: linear-gradient(110deg, #213b61 0%, #326590 100%);
            box-shadow: 0 5px 15px rgba(24, 43, 73, 0.21);
        }
        [data-testid="stDownloadButton"] > button:hover p { color: #ffffff; }
        [data-testid="stAlert"] {
            color: #34465d;
            border: 1px solid rgba(82, 97, 116, 0.16);
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(24, 43, 73, 0.035);
            padding-top: 0.65rem;
            padding-bottom: 0.65rem;
        }
        [data-testid="stAlert"] p {
            color: #34465d;
            font-size: 0.76rem;
            line-height: 1.45;
        }
        [data-testid="stProgress"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stProgress"] [data-testid="stMarkdownContainer"] span {
            color: #34465d;
        }
        [data-testid="stExpander"] details {
            overflow: hidden;
            background: #ffffff;
            border: 1px solid #dfe5ec;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(24, 43, 73, 0.035);
        }
        [data-testid="stExpander"] summary {
            min-height: 2.7rem;
            color: #344d69;
            font-size: 0.76rem;
            font-weight: 710;
        }
        [data-testid="stExpander"] summary * { color: #344d69; }
        [data-testid="stExpander"] details[open] summary {
            background: #f5f8fb;
            border-bottom: 1px solid #e2e7ed;
        }
        [data-testid="stExpander"] + [data-testid="stExpander"] {
            margin-top: 0.35rem;
        }
        [data-testid="stDivider"] { margin: 1.15rem 0; }
        .scope-note {
            color: #526174;
            background: #eef3f8;
            border: 1px solid #dce5ee;
            border-radius: 8px;
            padding: 0.65rem 0.8rem;
            margin-bottom: 1rem;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title) {
            background: #ffffff;
            border: 1px solid #dce4ed;
            border-radius: 14px;
            box-shadow: 0 5px 18px rgba(24, 43, 73, 0.065);
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        > div[data-testid="stVerticalBlock"] {
            gap: 0.65rem;
            padding: 1.15rem 1.2rem 1rem;
        }
        .analysis-setup-title {
            color: var(--dashboard-navy);
            font-size: 1.08rem;
            font-weight: 780;
            letter-spacing: -0.018em;
            margin-bottom: 0.18rem;
        }
        .analysis-setup-copy {
            color: var(--dashboard-muted);
            font-size: 0.78rem;
            line-height: 1.45;
            margin-bottom: 0.25rem;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        [data-testid="stWidgetLabel"] p {
            color: #34465d;
            font-size: 0.78rem;
            font-weight: 720;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        [data-baseweb="select"] > div,
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        [data-testid="stNumberInputContainer"] {
            min-height: 2.8rem;
            border-radius: 9px;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        [data-baseweb="select"] > div,
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        [data-baseweb="select"] span,
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        [data-baseweb="select"] input {
            color: #27364b;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        [data-testid="stNumberInputContainer"] input {
            color: #27364b;
            -webkit-text-fill-color: #27364b;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        .stButton > button[kind="primary"] {
            min-height: 2.8rem;
            color: #ffffff;
            border: 1px solid #182b49;
            border-radius: 9px;
            background: linear-gradient(110deg, #182b49 0%, #28547e 100%);
            box-shadow: 0 5px 13px rgba(24, 43, 73, 0.2);
            font-weight: 760;
            letter-spacing: 0.01em;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        .stButton > button[kind="primary"] p { color: #ffffff; }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        .stButton > button[kind="primary"]:hover {
            color: #ffffff;
            border-color: #244d78;
            background: linear-gradient(110deg, #213b61 0%, #326590 100%);
            box-shadow: 0 6px 16px rgba(24, 43, 73, 0.25);
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        .stButton > button[kind="primary"]:hover p { color: #ffffff; }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        .stButton > button[kind="primary"]:disabled {
            color: #788596;
            background: #e9edf2;
            border-color: #d4dbe4;
            box-shadow: none;
        }
        [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
        .stButton > button[kind="primary"]:disabled p { color: #788596; }
        [data-testid="stCaptionContainer"],
        [data-testid="stCaptionContainer"] p {
            color: #657286;
        }
        [data-testid="stTooltipContent"] p,
        [data-testid="stTooltipErrorContent"] p {
            color: inherit;
        }
        .setup-support {
            color: #718095;
            font-size: 0.71rem;
            line-height: 1.45;
            margin-top: -0.05rem;
        }
        .filing-years {
            display: flex;
            align-items: flex-start;
            gap: 0.55rem;
            color: #536276;
            background: #f5f8fb;
            border: 1px solid #e1e7ee;
            border-radius: 8px;
            padding: 0.62rem 0.72rem;
            font-size: 0.73rem;
            line-height: 1.45;
        }
        .filing-years-label {
            color: #344d69;
            font-weight: 760;
            white-space: nowrap;
        }
        @media (max-width: 900px) {
            [data-testid="stSidebar"],
            [data-testid="stSidebar"] > div:first-child {
                min-width: 245px !important;
                max-width: 245px !important;
                width: 245px !important;
            }
            .block-container { padding: 0.85rem 0.9rem 1.4rem; }
            .dashboard-header-row { align-items: flex-start; flex-direction: column; }
            .dashboard-scope { white-space: normal; }
            .analysis-banner { align-items: flex-start; flex-direction: column; }
            .overview-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .overview-summary-item:nth-child(3) { border-left: 0; }
            .overview-summary-item:nth-child(n+3) {
                border-top: 1px solid rgba(255, 255, 255, 0.13);
            }
            .red-flag-summary { grid-template-columns: 1fr; }
            .section-heading-copy { max-width: none; }
            [data-testid="stLayoutWrapper"]:has(.analysis-setup-title)
            [data-testid="stHorizontalBlock"] { row-gap: 1rem; }
            .st-key-analysis_navigation > div[data-baseweb="tab-panel"] {
                padding-top: 0.65rem;
            }
            [data-testid="stMetric"] { min-height: 98px; }
        }
        @media (max-width: 560px) {
            .dashboard-title { font-size: 1.85rem; }
            .dashboard-header { padding-bottom: 0.9rem; margin-bottom: 0.9rem; }
            .section-heading { margin-bottom: 0.65rem; }
            .section-heading-title { font-size: 1.08rem; }
            .section-heading-copy { font-size: 0.75rem; }
            .overview-summary { grid-template-columns: 1fr; }
            .overview-summary-item,
            .overview-summary-item:nth-child(3) {
                border-left: 0;
                border-top: 1px solid rgba(255, 255, 255, 0.13);
            }
            .overview-summary-item:first-child { border-top: 0; }
            .section-status-heading { align-items: flex-start; flex-direction: column; }
            .section-status-grid { grid-template-columns: 1fr; }
            .interpretation-card-header { flex-direction: column; }
            .analysis-banner { padding: 0.78rem 0.85rem; }
            .filing-years { flex-direction: column; gap: 0.2rem; }
            .filing-years-label { white-space: normal; }
            .st-key-analysis_navigation > div[data-baseweb="tab-list"] {
                border-radius: 10px;
                padding: 0.3rem;
            }
            .stTabs [data-baseweb="tab-panel"] { padding: 0.75rem; }
            .st-key-analysis_navigation > div[data-baseweb="tab-panel"] {
                padding: 0.55rem 0 0.8rem;
            }
            [data-testid="stAlert"] { padding: 0.55rem 0.65rem; }
            [data-testid="stDataFrame"],
            [data-testid="stVegaLiteChart"],
            [data-testid="stArrowVegaLiteChart"] { border-radius: 9px; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def _extracted_frame(result: PipelineResult) -> pd.DataFrame:
    """Create a display/correction frame without changing extracted values."""

    if isinstance(result.corrected_data, pd.DataFrame):
        return result.corrected_data.copy(deep=True)
    statements = result.extracted_data
    rows = []
    for value in getattr(statements, "values", ()):
        rows.append(
            {
                "Company": statements.company_name,
                "Ticker": statements.ticker,
                "Fiscal Year": value.fiscal_year,
                "Metric": value.financial_field,
                "Value": value.raw_value,
                "Raw Unit": value.unit,
                "Units": value.unit,
                "Financial Statement": value.financial_statement,
                "Source": value.source_url,
                "Source Date": value.filing_date,
                "Status": value.status,
                "Period Start": value.period_start,
                "Period End": value.period_end,
                "Filing Form": value.filing_form,
                "Accession Number": value.accession_number,
                "SEC Source Identifier": value.sec_source_identifier,
                "XBRL Taxonomy": value.xbrl_taxonomy,
                "XBRL Concept": value.xbrl_concept,
                "Missing Reason": value.missing_reason,
                "Validation Reason": value.validation_reason,
            }
        )
    return pd.DataFrame(rows)


_MONETARY_COLUMN_MARKERS = (
    "revenue",
    "net income",
    "cash flow",
    "free cash flow",
    "receivable",
    "inventory",
    "accounts payable",
    "ar change",
    "ap change",
    "capital expenditure",
    "capex",
    "depreciation",
    "deferred tax",
    "tax expense",
    "stock-based compensation",
    "sbc",
    "cash spent",
    "working capital cash effect",
    "normalization adjustment",
)

_FINANCIAL_METRIC_UNIT_ALIASES = {
    "Free Cash Flow": "Operating Cash Flow",
    "AR Change": "Accounts Receivable",
    "Inventory Change": "Inventory",
    "AP Change": "Accounts Payable",
    "Net Working Capital Cash Effect": "Operating Cash Flow",
    "SBC": "Stock-Based Compensation",
    "Reported Net Income": "Net Income",
    "Normalized Net Income": "Net Income",
    "Normalization Difference": "Net Income",
    "Normalization Adjustment": "Net Income",
    "Difference": "Net Income",
}


def _compact_currency_from_millions(value: Real) -> str:
    """Display pipeline monetary values, which are normalized to USD millions."""

    amount = float(value)
    absolute = abs(amount)
    if absolute >= 1_000:
        text = f"${absolute / 1_000:,.1f}B"
    else:
        text = f"${absolute:,.1f}M"
    return f"({text})" if amount < 0 else text


def _compact_currency(value: Real) -> str:
    amount = float(value)
    absolute = abs(amount)
    if absolute >= 1_000_000_000:
        text = f"${absolute / 1_000_000_000:,.1f}B"
    elif absolute >= 1_000_000:
        text = f"${absolute / 1_000_000:,.1f}M"
    elif absolute >= 1_000:
        text = f"${absolute / 1_000:,.1f}K"
    else:
        text = f"${absolute:,.0f}"
    return f"({text})" if amount < 0 else text


def _is_usd_millions(unit: Any) -> bool:
    normalized = str(unit or "").casefold()
    return "usd" in normalized and "million" in normalized


def _is_raw_usd(unit: Any) -> bool:
    normalized = str(unit or "").casefold()
    return "usd" in normalized and "million" not in normalized


def _format_monetary_value(
    value: Any, unit: Any, *, missing: str = "—"
) -> str:
    """Format a monetary display value using its stored unit."""

    if _is_missing_display_value(value):
        return missing
    if _is_usd_millions(unit):
        return _compact_currency_from_millions(value)
    if _is_raw_usd(unit):
        return _compact_currency(value)
    return _compact_currency_from_millions(value)


def _monetary_value_in_usd(value: Any, unit: Any) -> Any:
    """Return a chart-only USD display value without mutating source data."""

    if _is_missing_display_value(value):
        return value
    amount = float(value)
    return amount * 1_000_000 if _is_usd_millions(unit) else amount


def _financial_unit_lookup(raw_data: Any) -> dict[str, str]:
    if not isinstance(raw_data, pd.DataFrame) or raw_data.empty:
        return {}
    unit_column = "Units" if "Units" in raw_data.columns else "Raw Unit"
    if not {"Metric", unit_column}.issubset(raw_data.columns):
        return {}
    available = raw_data.dropna(subset=["Metric", unit_column]).drop_duplicates(
        subset=["Metric"], keep="last"
    )
    return dict(zip(available["Metric"].astype(str), available[unit_column].astype(str)))


def _monetary_units_for_columns(
    columns: Any, raw_data: Any
) -> dict[str, str]:
    source_units = _financial_unit_lookup(raw_data)
    units = {}
    for column in columns:
        column_name = str(column)
        source_metric = _FINANCIAL_METRIC_UNIT_ALIASES.get(column_name, column_name)
        if source_metric in source_units and _is_monetary_column(
            column_name.casefold()
        ):
            units[column_name] = source_units[source_metric]
    return units


def _is_monetary_column(column_name: str) -> bool:
    return any(marker in column_name for marker in _MONETARY_COLUMN_MARKERS)


def _is_missing_display_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _display_value(value: Any, column: Any, unit: Any = None) -> str:
    """Format table values for readability without changing their data types."""

    if _is_missing_display_value(value):
        return "—"
    column_name = str(column).casefold()
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Real):
        if "fiscal year" in column_name:
            return f"{int(value)}"
        is_percentage = any(
            marker in column_name
            for marker in ("growth", "ratio", "percentage", " / ")
        ) or column_name.endswith("gap")
        if is_percentage:
            return f"{value:.2%}"
        if _is_monetary_column(column_name):
            return _format_monetary_value(value, unit or "USD millions")
        if float(value).is_integer():
            return f"{value:,.0f}"
        return f"{value:,.2f}"
    return str(value)


def _show_frame(
    frame: Any,
    *,
    empty_message: str,
    height: int = 420,
    monetary_units: Mapping[str, str] | None = None,
) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.info(empty_message)
        return

    severity_columns = [
        column
        for column in frame.columns
        if "severity" in str(column).casefold()
    ]
    status_columns = [
        column
        for column in frame.columns
        if str(column).casefold().endswith(("result", "status"))
    ]

    def severity_style(value: Any) -> str:
        normalized = str(value).casefold()
        if normalized == "unavailable":
            return "background-color:#eef1f5;color:#596778;font-weight:700"
        if normalized in {"high", "material concern", "weak"}:
            return "background-color:#fdecee;color:#8f2530;font-weight:700"
        if normalized in {"medium", "needs investigation"}:
            return "background-color:#fff2cc;color:#765600;font-weight:700"
        if normalized in {"low", "low risk", "none", "generally healthy", "strong"}:
            return "background-color:#e7f5eb;color:#276738;font-weight:700"
        return ""

    def status_style(value: Any) -> str:
        normalized = str(value).casefold()
        if normalized == "unavailable":
            return "background-color:#eef1f5;color:#596778;font-weight:700"
        if normalized in {"flag", "active manual correction", "missing", "invalid"}:
            return "background-color:#fdecee;color:#8f2530;font-weight:700"
        if normalized in {"review", "reverted manual correction"}:
            return "background-color:#fff2cc;color:#765600;font-weight:700"
        if normalized in {"no flag", "retrieved", "validated"}:
            return "background-color:#e7f5eb;color:#276738;font-weight:700"
        return ""

    displayed: Any = frame.style.format(
        {
            column: (
                lambda value, name=column: _display_value(
                    value, name, (monetary_units or {}).get(str(name))
                )
            )
            for column in frame.columns
        },
        na_rep="—",
    )
    if severity_columns:
        displayed = displayed.map(severity_style, subset=severity_columns)
    if status_columns:
        displayed = displayed.map(status_style, subset=status_columns)
    st.dataframe(displayed, width="stretch", hide_index=True, height=height)


def _section_heading(title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <div>
                <div class="section-heading-title">{escape(title)}</div>
                <div class="section-heading-copy">{escape(copy)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _section_summary(frame: Any) -> None:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return
    years = (
        sorted(frame["Fiscal Year"].dropna().astype(int).unique())
        if "Fiscal Year" in frame.columns
        else []
    )
    severity_columns = [
        column for column in frame.columns if "severity" in str(column).casefold()
    ]
    severity_outputs = 0
    for column in severity_columns:
        severity_outputs += int(
            frame[column]
            .astype(str)
            .str.casefold()
            .isin({"low", "medium", "high"})
            .sum()
        )
    period_text = (
        f"{len(years)} fiscal year{'s' if len(years) != 1 else ''}, through FY {years[-1]}"
        if years
        else f"{len(frame):,} result rows"
    )
    severity_text = (
        f" · {severity_outputs} existing non-neutral severity output(s) highlighted"
        if severity_columns
        else ""
    )
    st.markdown(
        f'<div class="section-summary">Showing {period_text}{severity_text}.</div>',
        unsafe_allow_html=True,
    )


def _status_tone_class(value: Any) -> str:
    """Map an existing status value to the same presentation tones as tables."""

    if _is_missing_display_value(value):
        return "status-tone-unavailable"
    normalized = str(value).casefold()
    if normalized == "unavailable":
        return "status-tone-unavailable"
    if normalized in {
        "high",
        "material concern",
        "weak",
        "flag",
        "active manual correction",
        "missing",
        "invalid",
    }:
        return "status-tone-concern"
    if normalized in {"medium", "needs investigation", "review", "reverted manual correction"}:
        return "status-tone-review"
    if normalized in {
        "low",
        "low risk",
        "none",
        "generally healthy",
        "strong",
        "no flag",
        "retrieved",
        "validated",
    }:
        return "status-tone-clear"
    return "status-tone-default"


def _section_status_snapshot(
    frame: Any,
    *,
    columns: tuple[str, ...],
    label_overrides: Mapping[str, str] | None = None,
) -> None:
    """Surface exact latest-year status outputs without replacing the full table."""

    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return
    latest = (
        frame.sort_values("Fiscal Year").iloc[-1]
        if "Fiscal Year" in frame.columns
        else frame.iloc[-1]
    )
    available_columns = [column for column in columns if column in frame.columns]
    if not available_columns:
        return
    fiscal_year = (
        _display_value(latest.get("Fiscal Year"), "Fiscal Year")
        if "Fiscal Year" in frame.columns
        else "Latest result"
    )
    cards = []
    for column in available_columns:
        value = latest.get(column)
        label = (label_overrides or {}).get(column, column)
        cards.append(
            '<div class="section-status-card '
            + _status_tone_class(value)
            + '"><div class="section-status-label">'
            + escape(str(label))
            + '</div><div class="section-status-value">'
            + escape(_display_value(value, column))
            + "</div></div>"
        )
    st.markdown(
        '<div class="section-status-heading">'
        '<div class="section-status-title">Latest reported status</div>'
        f'<div class="section-status-period">Fiscal year {escape(fiscal_year)}</div>'
        '</div><div class="section-status-grid">'
        + "".join(cards)
        + "</div>",
        unsafe_allow_html=True,
    )


def _financial_statement_table(raw_data: pd.DataFrame) -> None:
    required = {"Metric", "Fiscal Year", "Value"}
    if raw_data.empty or not required.issubset(raw_data.columns):
        _show_frame(raw_data, empty_message="No extracted financial records are available.")
        return
    statement = raw_data.pivot_table(
        index="Metric",
        columns="Fiscal Year",
        values="Value",
        aggfunc="first",
        dropna=False,
    ).reset_index()
    statement.columns = [
        str(int(column)) if isinstance(column, (int, float)) else str(column)
        for column in statement.columns
    ]
    unit_column = "Units" if "Units" in raw_data.columns else "Raw Unit"
    unit_lookup = (
        raw_data.drop_duplicates(subset=["Metric", "Fiscal Year"])
        .set_index(["Metric", "Fiscal Year"])[unit_column]
        .to_dict()
        if unit_column in raw_data.columns
        else {}
    )
    year_columns = [column for column in statement.columns if column != "Metric"]
    statement[year_columns] = statement[year_columns].astype(object)
    for row_index, row in statement.iterrows():
        metric = row["Metric"]
        for year_column in year_columns:
            value = row[year_column]
            if pd.isna(value):
                statement.at[row_index, year_column] = "—"
                continue
            unit = str(unit_lookup.get((metric, int(year_column)), "")).casefold()
            if "usd" in unit:
                displayed_value = _format_monetary_value(value, unit)
            elif "share" in unit and "million" in unit:
                displayed_value = f"{float(value) / 1_000:,.1f}B shares"
            else:
                displayed_value = _display_value(value, metric)
            statement.at[row_index, year_column] = displayed_value
    _show_frame(
        statement,
        empty_message="No extracted financial records are available.",
        height=min(520, 84 + 35 * len(statement)),
    )


def _format_kpi(value: Any, unit: Any = "USD millions") -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    if isinstance(value, Real):
        return _format_monetary_value(value, unit, missing="Unavailable")
    return str(value)


def _financial_kpi_cards(
    summary: Any, analysis: dict[str, Any], raw_data: Any = None
) -> None:
    if not isinstance(summary, pd.DataFrame) or summary.empty:
        return
    latest = summary.sort_values("Fiscal Year").iloc[-1]
    overall = analysis.get("overall_severity")
    overall_value = (
        overall.iloc[0].get("Benchmark Severity", "Unavailable")
        if isinstance(overall, pd.DataFrame) and not overall.empty
        else "Unavailable"
    )
    monetary_units = _monetary_units_for_columns(summary.columns, raw_data)
    cards = st.columns(5, gap="small")
    cards[0].metric("Latest Fiscal Year", str(int(latest["Fiscal Year"])))
    cards[1].metric(
        "Revenue", _format_kpi(latest.get("Revenue"), monetary_units.get("Revenue"))
    )
    cards[2].metric(
        "Net Income",
        _format_kpi(latest.get("Net Income"), monetary_units.get("Net Income")),
    )
    cards[3].metric(
        "Free Cash Flow",
        _format_kpi(
            latest.get("Free Cash Flow"), monetary_units.get("Free Cash Flow")
        ),
    )
    cards[4].metric("Overall Severity", str(overall_value))


def _severity_cards(analysis: dict[str, Any]) -> None:
    overall = analysis.get("overall_severity")
    yearly = analysis.get("fiscal_year_severity")
    detail = analysis.get("detailed_severity")
    overall_value = (
        str(overall.iloc[0].get("Benchmark Severity", "Unavailable"))
        if isinstance(overall, pd.DataFrame) and not overall.empty
        else "Unavailable"
    )
    st.markdown(
        '<div class="red-flag-summary">'
        f'<div class="red-flag-summary-card {_status_tone_class(overall_value)}">'
        '<div class="red-flag-summary-label">Overall severity</div>'
        f'<div class="red-flag-summary-value">{escape(overall_value)}</div></div>'
        '<div class="red-flag-summary-card"><div class="red-flag-summary-label">'
        'Fiscal years assessed</div><div class="red-flag-summary-value">'
        f'{len(yearly) if isinstance(yearly, pd.DataFrame) else 0}</div></div>'
        '<div class="red-flag-summary-card"><div class="red-flag-summary-label">'
        'Rule results</div><div class="red-flag-summary-value">'
        f'{len(detail) if isinstance(detail, pd.DataFrame) else 0}</div></div></div>'
        '<div class="severity-legend"><span class="severity-legend-label">Severity labels</span>'
        '<span class="severity-chip low">Low Risk</span>'
        '<span class="severity-chip investigation">Needs Investigation</span>'
        '<span class="severity-chip concern">Material Concern</span>'
        '<span class="severity-chip unavailable">Unavailable</span></div>',
        unsafe_allow_html=True,
    )


_USD_AXIS_LABEL_EXPRESSION = (
    "abs(datum.value) >= 1e9 ? format(datum.value / 1e9, '.1f') + 'B' : "
    "abs(datum.value) >= 1e6 ? format(datum.value / 1e6, '.1f') + 'M' : "
    "abs(datum.value) >= 1e3 ? format(datum.value / 1e3, '.1f') + 'K' : "
    "format(datum.value, ',.0f')"
)


def _financial_chart(summary: pd.DataFrame, raw_data: Any = None) -> None:
    chart_columns = [
        column
        for column in ("Revenue", "Net Income", "Operating Cash Flow", "Free Cash Flow")
        if column in summary.columns
    ]
    if not chart_columns or "Fiscal Year" not in summary.columns:
        return
    chart_data = summary[["Fiscal Year", *chart_columns]].melt(
        "Fiscal Year", var_name="Metric", value_name="Value"
    ).dropna(subset=["Value"])
    monetary_units = _monetary_units_for_columns(chart_columns, raw_data)
    chart_data["Stored Unit"] = chart_data["Metric"].map(monetary_units).fillna(
        "USD millions"
    )
    chart_data["Display Value"] = chart_data.apply(
        lambda row: _monetary_value_in_usd(row["Value"], row["Stored Unit"]),
        axis=1,
    )
    chart_data["Formatted Value"] = chart_data.apply(
        lambda row: _format_monetary_value(row["Value"], row["Stored Unit"]),
        axis=1,
    )
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("Fiscal Year:O", title="Fiscal Year"),
            y=alt.Y(
                "Display Value:Q",
                title="USD",
                axis=alt.Axis(
                    labelExpr=_USD_AXIS_LABEL_EXPRESSION,
                    gridColor="#e7ebf0",
                ),
            ),
            color=alt.Color(
                "Metric:N",
                title="Metric",
                scale=alt.Scale(
                    range=["#1f4e78", "#2f855a", "#805ad5", "#d69e2e"]
                ),
            ),
            tooltip=[
                "Fiscal Year:O", "Metric:N",
                alt.Tooltip("Formatted Value:N", title="Value"),
            ],
        )
        .properties(height=340, background="#ffffff")
    )
    st.altair_chart(chart, width="stretch")


def _analysis_chart(
    frame: Any,
    *,
    columns: tuple[str, ...],
    title: str,
    y_title: str,
    percentage: bool = False,
    bars: bool = False,
    monetary_units: Mapping[str, str] | None = None,
) -> None:
    """Render a consistent fiscal-year chart from existing output columns."""

    if not isinstance(frame, pd.DataFrame) or "Fiscal Year" not in frame.columns:
        return
    available = [column for column in columns if column in frame.columns]
    if not available:
        return
    chart_data = frame[["Fiscal Year", *available]].copy()
    for column in available:
        chart_data[column] = pd.to_numeric(chart_data[column], errors="coerce")
    chart_data = chart_data.melt(
        "Fiscal Year", var_name="Metric", value_name="Value"
    ).dropna(subset=["Value"])
    if chart_data.empty:
        return
    value_field = "Value"
    tooltip: Any = alt.Tooltip(
        "Value:Q", title="Value", format=".2%" if percentage else ",.2f"
    )
    axis_title = y_title
    axis_options: dict[str, Any] = {
        "format": ".1%" if percentage else "~s",
        "gridColor": "#e7ebf0",
        "gridOpacity": 0.9,
    }
    if monetary_units and not percentage:
        chart_data["Stored Unit"] = chart_data["Metric"].map(
            monetary_units
        ).fillna("USD millions")
        chart_data["Display Value"] = chart_data.apply(
            lambda row: _monetary_value_in_usd(
                row["Value"], row["Stored Unit"]
            ),
            axis=1,
        )
        chart_data["Formatted Value"] = chart_data.apply(
            lambda row: _format_monetary_value(
                row["Value"], row["Stored Unit"]
            ),
            axis=1,
        )
        value_field = "Display Value"
        tooltip = alt.Tooltip("Formatted Value:N", title="Value")
        axis_title = "USD"
        axis_options = {
            "labelExpr": _USD_AXIS_LABEL_EXPRESSION,
            "gridColor": "#e7ebf0",
            "gridOpacity": 0.9,
        }

    palette = ["#1f4e78", "#2f855a", "#d69e2e", "#805ad5"]
    base = alt.Chart(chart_data).encode(
        x=alt.X("Fiscal Year:O", title="Fiscal Year", axis=alt.Axis(labelAngle=0)),
        y=alt.Y(
            f"{value_field}:Q",
            title=axis_title,
            axis=alt.Axis(**axis_options),
        ),
        color=alt.Color(
            "Metric:N",
            title=None,
            scale=alt.Scale(domain=available, range=palette[: len(available)]),
        ),
        tooltip=[
            alt.Tooltip("Fiscal Year:O", title="Fiscal Year"),
            alt.Tooltip("Metric:N"),
            tooltip,
        ],
    )
    marks = (
        base.encode(xOffset="Metric:N").mark_bar(
            cornerRadiusTopLeft=3, cornerRadiusTopRight=3, opacity=0.88
        )
        if bars
        else base.mark_line(point=alt.OverlayMarkDef(size=72), strokeWidth=2.6)
    )
    st.markdown(
        '<div class="analysis-content-label">Multi-year trend</div>',
        unsafe_allow_html=True,
    )
    chart = marks.properties(title=title, height=310, background="#ffffff")
    st.altair_chart(chart, width="stretch")
    st.markdown(
        '<div class="chart-caption">Hover over the chart for the underlying pipeline value.</div>',
        unsafe_allow_html=True,
    )


_HUMAN_RULE_LABELS = {
    "AR growth vs Revenue growth": "Customer receivables compared with revenue",
    "Net Income growth vs OCF growth": "Earnings compared with operating cash flow",
    "Inventory growth vs Revenue growth": "Inventory compared with revenue",
    "CapEx vs D&A": "Investment spending compared with depreciation",
    "Accounts Payable pattern": "Supplier-payment pattern",
    "Deferred Tax Asset risk": "Deferred-tax-asset recoverability",
    "SBC dilution": "Stock compensation and shareholder dilution",
    "Repeated one-off items": "Repeated adjustments described as one-off",
}


def _humanized_narrative(value: Any) -> str:
    """Make pipeline prose easier to scan while retaining its exact meaning."""

    text = str(value or "Unavailable")
    replacements = (
        ("Task 90 input", "available analysis"),
        ("supplied fiscal-year results", "fiscal-year results"),
        ("Supplied fiscal-year results", "Fiscal-year results"),
        ("under the supplied rules", "under the current review criteria"),
        ("under the supplied tests", "under the current review criteria"),
        ("The existing ", "The "),
        ("rule did not trigger", "review condition was not met"),
        ("rule triggered", "review condition was met"),
        ("warning.", "review signal."),
        ("warnings.", "review signals."),
    )
    for original, replacement in replacements:
        text = text.replace(original, replacement)
    return text


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple)):
        return list(value)
    return [] if value is None else [value]


def _latest_supplied_severity(interpretation: Mapping[str, Any]) -> str:
    severities = [
        item
        for item in _as_list(interpretation.get("existing_severities"))
        if isinstance(item, Mapping)
    ]
    if not severities:
        return "Severity unavailable"
    latest = sorted(
        severities,
        key=lambda item: int(item.get("fiscal_year") or 0),
    )[-1]
    severity = latest.get("severity")
    year = latest.get("fiscal_year")
    return f"FY {year}: {severity if severity is not None else 'Unavailable'}"


def _status_tone(label: str, has_concerns: bool = False) -> str:
    normalized = label.casefold()
    if "unavailable" in normalized:
        return "status-unavailable"
    if any(word in normalized for word in ("high", "material concern", "weak")):
        return "status-concern"
    if has_concerns or any(
        word in normalized for word in ("medium", "investigation", "review")
    ):
        return "status-review"
    return "status-clear"


def _signal_list_html(signals: list[Any], empty_message: str) -> str:
    if not signals:
        return f'<div class="interpretation-copy">{escape(empty_message)}</div>'
    items = "".join(
        f"<li>{escape(_humanized_narrative(signal))}</li>" for signal in signals
    )
    return f'<ul class="signal-list">{items}</ul>'


def _render_interpretation_card(interpretation: Mapping[str, Any]) -> None:
    area = str(interpretation.get("area") or "Analysis area")
    assessment = _humanized_narrative(
        interpretation.get("overall_assessment") or interpretation.get("explanation")
    )
    concerns = _as_list(
        interpretation.get("key_concerns", interpretation.get("concerns"))
    )
    positives = _as_list(
        interpretation.get(
            "key_positive_signals", interpretation.get("positive_signals")
        )
    )
    unavailable = []
    for yearly in _as_list(interpretation.get("yearly_assessments")):
        if not isinstance(yearly, Mapping):
            continue
        evidence = _as_list(yearly.get("unavailable_evidence"))
        if evidence:
            fiscal_year = yearly.get("fiscal_year", "Unavailable")
            unavailable.append(
                f"FY {fiscal_year}: " + ", ".join(str(item) for item in evidence)
            )
    severity_label = _latest_supplied_severity(interpretation)
    tone = _status_tone(severity_label, bool(concerns))
    st.markdown(
        f"""
        <div class="interpretation-card">
            <div class="interpretation-card-header">
                <div>
                    <div class="interpretation-label">Investor review area</div>
                    <div class="interpretation-title">{escape(area)}</div>
                </div>
                <span class="status-badge {tone}">{escape(severity_label)}</span>
            </div>
            <div class="interpretation-section assessment">
                <div class="interpretation-label">Overall assessment</div>
                <div class="interpretation-copy">{escape(assessment)}</div>
            </div>
            <div class="interpretation-section concerns">
                <div class="interpretation-label">Key concerns</div>
                {_signal_list_html(concerns, "No key concern was supplied.")}
            </div>
            <div class="interpretation-section positives">
                <div class="interpretation-label">Positive signals</div>
                {_signal_list_html(positives, "No positive signal was supplied.")}
            </div>
            <div class="interpretation-section unavailable">
                <div class="interpretation-label">Unavailable evidence</div>
                {_signal_list_html(unavailable, "No unavailable evidence was supplied.")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _interpretation_detail_frame(interpretation: Mapping[str, Any]) -> pd.DataFrame:
    rows = []
    for item in _as_list(interpretation.get("yearly_assessments")):
        if not isinstance(item, Mapping):
            continue
        row = {
            "Fiscal Year": item.get("fiscal_year"),
            "Existing Severity": item.get("existing_severity"),
            "Exact Assessment": item.get("assessment"),
            "Exact Positive Signals": " | ".join(
                str(value)
                for value in _as_list(
                    item.get("positive_signals", item.get("positives"))
                )
            ),
            "Exact Concerns": " | ".join(
                str(value) for value in _as_list(item.get("concerns"))
            ),
            "Source Explanation": item.get("source_explanation"),
            "Unavailable Evidence": ", ".join(
                str(value) for value in _as_list(item.get("unavailable_evidence"))
            ),
        }
        evidence = item.get("supporting_evidence", item.get("evidence"))
        if isinstance(evidence, Mapping):
            for key, value in evidence.items():
                row[f"Evidence · {str(key).replace('_', ' ').title()}"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def _render_interpretations(interpretations: Mapping[str, Any]) -> None:
    final = interpretations.get("final_conclusion")
    if isinstance(final, Mapping):
        conclusion = str(
            final.get("earnings_quality_conclusion") or "Conclusion unavailable"
        )
        explanation = _humanized_narrative(final.get("explanation"))
        tone = _status_tone(conclusion, bool(final.get("key_concerns")))
        st.markdown(
            f"""
            <div class="conclusion-card">
                <div class="conclusion-label">Overall earnings-quality conclusion</div>
                <div class="conclusion-title">{escape(conclusion)}</div>
                <span class="status-badge {tone}">Existing pipeline conclusion</span>
                <div class="conclusion-copy">{escape(explanation)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="investor-note">
            These signals identify areas for further review. They are not proof of fraud,
            manipulation, or insolvency, and they are not a recommendation to buy or sell
            a security.
        </div>
        """,
        unsafe_allow_html=True,
    )

    ordered_keys = (
        "accrual",
        "working_capital",
        "capex",
        "deferred_taxes",
        "sbc",
        "normalized_earnings",
    )
    available = [
        (key, interpretations.get(key))
        for key in ordered_keys
        if isinstance(interpretations.get(key), Mapping)
    ]
    for start in range(0, len(available), 2):
        columns = st.columns(2, gap="medium")
        for column, (_, interpretation) in zip(columns, available[start : start + 2]):
            with column:
                _render_interpretation_card(interpretation)

    st.markdown("#### Methodology and exact interpretation details")
    st.caption(
        "The sections below preserve the pipeline's original wording, yearly evidence, flags, and severity labels."
    )
    for _, interpretation in available:
        area = str(interpretation.get("area") or "Analysis area")
        with st.expander(f"{area} · exact evidence and methodology", type="compact"):
            st.markdown("**Exact pipeline assessment**")
            st.write(interpretation.get("overall_assessment", "Unavailable"))
            st.markdown("**Exact pipeline explanation**")
            st.write(interpretation.get("explanation", "Unavailable"))
            detail_frame = _interpretation_detail_frame(interpretation)
            _show_frame(
                detail_frame,
                empty_message="No fiscal-year interpretation detail is available.",
                height=min(420, 82 + 38 * len(detail_frame)),
            )

    if isinstance(final, Mapping):
        with st.expander("Overall conclusion · exact supporting details", type="compact"):
            st.markdown("**Exact pipeline explanation**")
            st.write(final.get("explanation", "Unavailable"))
            overall_severity = final.get("existing_overall_severity")
            if isinstance(overall_severity, Mapping):
                st.markdown("**Exact existing overall severity**")
                _show_frame(
                    pd.DataFrame([overall_severity]),
                    empty_message="No overall severity was supplied.",
                    height=120,
                )
            concern_frame = pd.DataFrame(_as_list(final.get("key_concerns")))
            if not concern_frame.empty:
                st.markdown("**Exact concerns carried into the conclusion**")
                _show_frame(
                    concern_frame,
                    empty_message="No conclusion concerns were supplied.",
                    height=min(360, 82 + 38 * len(concern_frame)),
                )
            positive_frame = pd.DataFrame(
                _as_list(final.get("positive_signals"))
            )
            if not positive_frame.empty:
                st.markdown("**Exact positive signals carried into the conclusion**")
                _show_frame(
                    positive_frame,
                    empty_message="No positive conclusion signals were supplied.",
                    height=min(360, 82 + 38 * len(positive_frame)),
                )


def _humanized_red_flag_frame(analysis: Mapping[str, Any]) -> pd.DataFrame:
    detailed = analysis.get("detailed_severity")
    if not isinstance(detailed, pd.DataFrame) or detailed.empty:
        return pd.DataFrame()
    readable = detailed.copy(deep=True)
    readable["Metric"] = readable["Metric"].map(
        lambda value: _HUMAN_RULE_LABELS.get(str(value), str(value))
    )
    readable = readable.rename(
        columns={"Metric": "What Was Reviewed", "Result": "Status"}
    )
    preferred = [
        "Fiscal Year",
        "What Was Reviewed",
        "Status",
        "Internal Severity",
        "Final Severity",
        "Explanation",
    ]
    return readable[[column for column in preferred if column in readable.columns]]


def _show_investor_results(
    frame: Any,
    *,
    preferred_columns: tuple[str, ...],
    label_overrides: Mapping[str, str],
    empty_message: str,
    monetary_units: Mapping[str, str] | None = None,
) -> None:
    """Show a concise view and retain the complete source output for audit."""

    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.info(empty_message)
        return
    visible_columns = [
        column for column in preferred_columns if column in frame.columns
    ]
    readable = frame[visible_columns].copy(deep=True).rename(columns=label_overrides)
    readable_units = {
        label_overrides.get(column, column): unit
        for column, unit in (monetary_units or {}).items()
        if column in visible_columns
    }
    st.markdown(
        '<div class="analysis-content-label">Investor-facing results</div>'
        '<div class="investor-table-caption">Existing pipeline outputs; status and '
        'severity labels are unchanged.</div>',
        unsafe_allow_html=True,
    )
    _show_frame(
        readable,
        empty_message=empty_message,
        monetary_units=readable_units,
    )
    with st.expander(
        "Exact methodology, rules, formulas, and complete results", type="compact"
    ):
        st.caption(
            "This audit view is the complete pipeline table. Exact rules, thresholds, flags, results, severities, calculations, and explanations are unchanged."
        )
        _show_frame(
            frame,
            empty_message=empty_message,
            height=500,
            monetary_units=monetary_units,
        )


def _request_pipeline_run(company: str, years: int) -> None:
    corrections = tuple(st.session_state.manual_corrections.values())
    progress = st.progress(0, text=f"Starting {PIPELINE_STAGES[0]}...")
    completed_stages = 0

    def show_progress(stage: str, status: str) -> None:
        nonlocal completed_stages
        if status == "started":
            progress.progress(
                completed_stages / len(PIPELINE_STAGES),
                text=f"Current stage: {stage}",
            )
        elif status == "completed":
            completed_stages += 1
            progress.progress(
                completed_stages / len(PIPELINE_STAGES),
                text=f"Completed: {stage}",
            )

    try:
        with st.spinner("Retrieving SEC filings and running the analysis..."):
            result = run_pipeline(
                company,
                years,
                manual_corrections=corrections,
                progress_callback=show_progress,
            )
    except PipelineStageError as error:
        st.session_state.pipeline_result = None
        st.session_state.pipeline_error = str(error)
        st.session_state.pipeline_error_details = "".join(
            traceback.format_exception(
                type(error.original_error),
                error.original_error,
                error.original_error.__traceback__,
            )
        )
    except Exception as error:
        st.session_state.pipeline_result = None
        st.session_state.pipeline_error = str(error)
        st.session_state.pipeline_error_details = traceback.format_exc()
    else:
        st.session_state.pipeline_result = result
        st.session_state.pipeline_error = None
        st.session_state.pipeline_error_details = None
        st.session_state.last_company = company
        st.session_state.last_years = years


@st.cache_data(show_spinner=False, ttl=3600)
def _selectable_fiscal_years(ticker: str) -> tuple[int, ...]:
    return available_fiscal_years(ticker)


@st.cache_data(show_spinner="Loading the official SEC company list...", ttl=86400)
def _sec_company_options() -> tuple[Any, ...]:
    return sec_company_options()


def _default_fiscal_year_count(
    usable_year_count: int | None, previous_year_count: Any = None
) -> int:
    """Choose the initial year count without changing availability limits."""

    maximum = (
        10
        if usable_year_count is None
        else max(4, min(10, int(usable_year_count)))
    )
    try:
        previous = int(previous_year_count)
    except (TypeError, ValueError):
        previous = None
    if previous is not None and 4 <= previous <= maximum:
        return previous
    return min(5, maximum)


with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">Earnings Quality Analyzer</div>
            <div class="sidebar-brand-subtitle">
                From official filing data to a structured, investor-focused review.
            </div>
        </div>
        <div class="sidebar-label">Analysis platform</div>
        <div class="sidebar-feature">
            <div class="sidebar-feature-icon">SEC</div>
            <div><div class="sidebar-feature-title">Official filing data</div>
            <div class="sidebar-feature-copy">Search supported companies and retain SEC filing provenance.</div></div>
        </div>
        <div class="sidebar-feature">
            <div class="sidebar-feature-icon">10Y</div>
            <div><div class="sidebar-feature-title">Multi-year analysis</div>
            <div class="sidebar-feature-copy">Review four to ten usable annual fiscal periods.</div></div>
        </div>
        <div class="sidebar-feature">
            <div class="sidebar-feature-icon">CHK</div>
            <div><div class="sidebar-feature-title">Validation-aware analysis</div>
            <div class="sidebar-feature-copy">Validated available data continues through partial analysis while affected outputs remain unavailable.</div></div>
        </div>
        <div class="sidebar-feature">
            <div class="sidebar-feature-icon">XLS</div>
            <div><div class="sidebar-feature-title">Investor-ready output</div>
            <div class="sidebar-feature-copy">Structured interpretations and a company-specific workbook.</div></div>
        </div>
        <div class="scope-note">SEC-reporting non-financial companies only</div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Identification → SEC extraction → validation → calculations → rules → interpretation → Excel")

if "manual_corrections" not in st.session_state:
    st.session_state.manual_corrections = {}
if "manual_correction_history" not in st.session_state:
    st.session_state.manual_correction_history = []
if "pipeline_result" not in st.session_state:
    st.session_state.pipeline_result = None
if "pipeline_error" not in st.session_state:
    st.session_state.pipeline_error = None
if "pipeline_error_details" not in st.session_state:
    st.session_state.pipeline_error_details = None

st.markdown(
    """
    <div class="dashboard-header">
        <div class="dashboard-eyebrow">Financial statement intelligence</div>
        <h1 class="dashboard-title">Earnings Quality Analysis</h1>
        <div class="dashboard-header-row">
            <p class="dashboard-subtitle">
                Review multi-year filing data, accounting signals, and earnings-quality evidence.
            </p>
            <div class="dashboard-scope">
                <span class="dashboard-scope-dot"></span>
                SEC-reporting non-financial companies only
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    company_options = _sec_company_options()
    company_list_error = None
except Exception as error:
    company_options = ()
    company_list_error = str(error)
last_company = st.session_state.get("last_company")
default_company_index = next(
    (
        index + 1
        for index, option in enumerate(company_options)
        if option.ticker == last_company
    ),
    0,
)

with st.container(border=True):
    st.markdown(
        '<div class="analysis-setup-title">Set up the analysis</div>'
        '<div class="analysis-setup-copy">Choose a supported company and the annual '
        'review period.</div>',
        unsafe_allow_html=True,
    )
    company_column, years_column, analyze_column = st.columns(
        [2.55, 1.05, 0.95], gap="large", vertical_alignment="bottom"
    )
    with company_column:
        selected_company = st.selectbox(
            "Company / Ticker",
            options=(None, *company_options),
            index=default_company_index,
            format_func=(
                lambda option: (
                    "Select a company"
                    if option is None
                    else f"{option.company_name} ({option.ticker})"
                )
            ),
            help="Type part of a company name or ticker to search the supported list.",
        )
    company = selected_company.ticker if selected_company is not None else ""

    selectable_years = ()
    availability_error = None
    if selected_company is not None:
        try:
            selectable_years = _selectable_fiscal_years(selected_company.ticker)
        except Exception as error:
            availability_error = str(error)
    year_limit = min(10, len(selectable_years)) if selectable_years else 10
    has_minimum_history = len(selectable_years) >= 4
    default_years = _default_fiscal_year_count(
        len(selectable_years) if selected_company is not None else None,
        st.session_state.get("last_years"),
    )

    with years_column:
        years = int(
            st.number_input(
                "Number of Fiscal Years",
                min_value=4,
                max_value=max(4, year_limit),
                value=default_years,
                step=1,
                disabled=selected_company is not None and not has_minimum_history,
            )
        )
    with analyze_column:
        analyze_clicked = st.button(
            "Analyze",
            type="primary",
            width="stretch",
            disabled=(selected_company is None or not has_minimum_history),
        )

    st.markdown(
        f'<div class="setup-support">Search {len(company_options):,} supported '
        'companies by company name or ticker.</div>',
        unsafe_allow_html=True,
    )
    if company_list_error:
        st.error(
            f"The official SEC company list could not be loaded: {company_list_error}"
        )
    if selected_company is not None and selectable_years:
        st.markdown(
            '<div class="filing-years"><span class="filing-years-label">Available annual '
            'SEC filing years</span><span>'
            + ", ".join(str(year) for year in selectable_years)
            + "</span></div>",
            unsafe_allow_html=True,
        )
        if not has_minimum_history:
            st.error(
                "Analysis requires at least 4 usable SEC annual fiscal years; "
                f"only {len(selectable_years)} are available."
            )
    elif availability_error:
        st.error(
            "This supported company is currently unavailable because its SEC identity "
            "or usable annual filing history could not be verified. "
            f"Details: {availability_error}"
        )
    elif selected_company is not None:
        st.error(
            "This supported company is currently unavailable because no usable annual "
            "SEC filing years could be verified. Analysis requires at least 4 years."
        )

if analyze_clicked:
    if selected_company is None:
        st.session_state.pipeline_error = "Select a supported company."
        st.session_state.pipeline_error_details = None
    else:
        previous_company = st.session_state.get("last_company")
        if previous_company and previous_company.casefold() != company.strip().casefold():
            st.session_state.manual_corrections = {}
            st.session_state.manual_correction_history = []
        _request_pipeline_run(company.strip(), years)

if st.session_state.pipeline_error:
    st.error(st.session_state.pipeline_error)
    if st.session_state.pipeline_error_details:
        with st.expander("Technical details", type="compact"):
            st.code(st.session_state.pipeline_error_details)

result = st.session_state.pipeline_result
if result is None:
    st.info("Enter a company or ticker and select Analyze to begin.")
    st.stop()

selected_analysis_years = tuple(sorted(selectable_years)[-years:])
if not pipeline_result_matches_selection(
    result, selected_company, selected_analysis_years
):
    st.info(
        "The company or fiscal-year selection has changed. Select Analyze to "
        "generate the matching analysis and workbook."
    )
    st.stop()

raw_data = _extracted_frame(result)
company_name = escape(str(getattr(result.company, "company_name", "Selected company")))
company_ticker = escape(str(getattr(result.company, "ticker", "")))
validated_years = result.validation.requested_fiscal_years
st.markdown(
    f"""
    <div class="analysis-banner">
        <div>
            <div class="analysis-banner-title">{company_name} ({company_ticker})</div>
            <div class="analysis-banner-copy">
                Fiscal years {min(validated_years) if validated_years else 'Unavailable'}–{max(validated_years) if validated_years else 'Unavailable'}
                · {len(raw_data):,} extracted records · {len(st.session_state.manual_corrections)} correction overlay(s)
            </div>
        </div>
        <div class="analysis-banner-status">
            {'Validation blocked' if result.blocked else 'Partial analysis' if result.partial else 'Validation approved'}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
if result.partial and result.partial_notice:
    st.warning(result.partial_notice)
tabs = st.tabs(
    [
        "Financial Data",
        "Analysis",
        "Cash Conversion",
        "Working Capital",
        "Taxes",
        "SBC",
        "Normalized Earnings",
        "Red Flags",
        "Interpretations",
    ],
    key="analysis_navigation",
)

with tabs[0]:
    _section_heading(
        "Extracted Financial Data",
        "Review the annual statement values first, then open the source-record view for filing provenance and extraction details.",
    )
    statement_tab, provenance_tab = st.tabs(["Statement View", "Source & Provenance"])
    with statement_tab:
        _financial_statement_table(raw_data)
    with provenance_tab:
        _show_frame(
            raw_data,
            empty_message="No extracted financial records are available.",
            height=480,
        )

    if not raw_data.empty:
        with st.expander("Correct Extracted Data", expanded=result.blocked):
            st.markdown(
                '<div class="correction-shell"><strong>Manual correction workspace</strong><br>'
                'Select one extracted annual fact. The source record remains unchanged; '
                'an auditable correction overlay is applied to the next pipeline run.</div>',
                unsafe_allow_html=True,
            )
            fiscal_years = sorted(int(value) for value in raw_data["Fiscal Year"].unique())
            selector_year, selector_metric = st.columns([1, 2])
            selected_year = selector_year.selectbox("Fiscal year", fiscal_years)
            year_rows = raw_data.loc[raw_data["Fiscal Year"].eq(selected_year)]
            selected_metric = selector_metric.selectbox(
                "Metric", year_rows["Metric"].tolist()
            )
            selected = year_rows.loc[year_rows["Metric"].eq(selected_metric)].iloc[0].to_dict()
            correction_key = (selected_metric, selected_year)
            current_correction = st.session_state.manual_corrections.get(correction_key)
            effective_record = dict(selected)
            effective_record["Value"] = selected.get(
                "Original Value", selected.get("Value")
            )
            current_value = effective_value(effective_record, current_correction)
            value_missing = current_value is None or pd.isna(current_value)
            selected_unit = selected.get("Raw Unit") or selected.get("Units")
            selected_is_monetary = _is_raw_usd(selected_unit) or _is_usd_millions(
                selected_unit
            )

            details = st.columns(4)
            original_value = selected.get("Original Value", selected.get("Value"))
            details[0].metric(
                "Original SEC value",
                "Missing" if original_value is None or pd.isna(original_value)
                else (
                    _format_monetary_value(original_value, selected_unit)
                    if selected_is_monetary
                    else _display_value(original_value, "Value")
                ),
            )
            details[1].metric(
                "Effective value",
                "Missing"
                if value_missing
                else (
                    _format_monetary_value(current_value, selected_unit)
                    if selected_is_monetary
                    else _display_value(current_value, "Value")
                ),
            )
            details[2].metric(
                "Unit",
                str(selected_unit or "Unavailable"),
            )
            details[3].metric("Status", str(selected.get("Status", "Unavailable")))

            st.markdown(
                f"""
                <div class="correction-context">
                    <strong>Source context</strong><br>
                    Filing: {escape(str(selected.get('Filing Form') or 'Unavailable'))}
                    &nbsp;&middot;&nbsp; Filed: {escape(str(selected.get('Source Date') or 'Unavailable'))}
                    &nbsp;&middot;&nbsp; Period end: {escape(str(selected.get('Period End') or 'Unavailable'))}<br>
                    XBRL concept: {escape(str(selected.get('XBRL Concept') or 'Unavailable'))}
                </div>
                """,
                unsafe_allow_html=True,
            )

            correction_value_column, correction_reason_column = st.columns([1, 2])
            corrected_value = correction_value_column.number_input(
                "Corrected value",
                value=None if value_missing else float(current_value),
                placeholder="Enter the reviewed value",
                key=f"correction-value-{selected_year}-{selected_metric}",
            )
            correction_reason = correction_reason_column.text_area(
                "Correction reason (required)",
                placeholder="Document the evidence and reason for this correction.",
                height=96,
                key=f"correction-reason-{selected_year}-{selected_metric}",
            )
            apply_column, revert_column = st.columns(2)
            if apply_column.button("Apply Correction", type="primary", width="stretch"):
                try:
                    correction_record = dict(selected)
                    correction_record.update(
                        {
                            "raw_sec_value": selected.get(
                                "Original Value", selected.get("Value")
                            ),
                            "raw_unit": selected.get("Raw Unit") or selected.get("Units"),
                            "filing_form": selected.get("Filing Form"),
                            "filing_date": selected.get("Source Date"),
                            "accession_number": selected.get("Accession Number"),
                            "sec_source_identifier": selected.get("SEC Source Identifier"),
                            "source_url": selected.get("Source"),
                            "xbrl_taxonomy": selected.get("XBRL Taxonomy"),
                            "xbrl_concept": selected.get("XBRL Concept"),
                            "period_start": selected.get("Period Start"),
                            "period_end": selected.get("Period End"),
                            "status": selected.get("Status"),
                        }
                    )
                    correction = create_manual_correction(
                        correction_record,
                        corrected_value,
                        correction_reason,
                        corrected_unit=selected.get("Raw Unit") or selected.get("Units"),
                    )
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state.manual_corrections[correction_key] = correction
                    st.session_state.manual_correction_history.append(correction)
                    _request_pipeline_run(
                        st.session_state.last_company,
                        int(st.session_state.last_years),
                    )
                    st.rerun()
            if revert_column.button(
                "Revert Correction",
                disabled=not (current_correction and current_correction.is_active),
                width="stretch",
            ):
                reverted = revert_manual_correction(current_correction)
                st.session_state.manual_corrections[correction_key] = reverted
                st.session_state.manual_correction_history.append(reverted)
                _request_pipeline_run(
                    st.session_state.last_company,
                    int(st.session_state.last_years),
                )
                st.rerun()

            if st.session_state.manual_correction_history:
                st.markdown(
                    '<div class="audit-heading">Manual correction audit trail</div>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    "Every apply and revert action is retained in session order; original filing provenance remains attached to each correction."
                )
                audit_frame = pd.DataFrame(
                    [
                        {
                            "Action": index,
                            "Metric": item.metric,
                            "Fiscal Year": item.fiscal_year,
                            "Original Value": item.original_value,
                            "Corrected Value": item.corrected_value,
                            "Unit": item.original_unit,
                            "Reason": item.correction_reason,
                            "Status": item.correction_status.value,
                            "Filing Form": item.original_provenance.filing_form,
                            "Filing Date": item.original_provenance.filing_date,
                        }
                        for index, item in enumerate(
                            st.session_state.manual_correction_history, start=1
                        )
                    ]
                ).sort_values("Action", ascending=False)
                _show_frame(
                    audit_frame,
                    empty_message="No manual correction actions have been recorded.",
                    height=min(360, 76 + 35 * len(audit_frame)),
                )

if result.blocked:
    st.error("Analysis stopped because critical validation requirements were not satisfied.")
    if result.validation.blocking_issues:
        st.dataframe(
            [
                {
                    "Fiscal Year": issue.fiscal_year,
                    "Metric": issue.metric,
                    "Validation Source": issue.validation_source,
                    "Status": issue.blocking_status,
                    "Explanation": issue.explanation,
                }
                for issue in result.validation.blocking_issues
            ],
            width="stretch",
            hide_index=True,
        )
    for tab in tabs[1:]:
        with tab:
            st.info("Unavailable until the validation issues are resolved.")
    st.stop()

calculations = result.calculations or {}
analysis = result.red_flags_and_severity or {}

with tabs[1]:
    _section_heading(
        "Analysis Overview",
        "A consolidated multi-year view of the reported statement values and existing pipeline calculations.",
    )
    summary = calculations.get("financial_summary")
    summary_units = (
        _monetary_units_for_columns(summary.columns, raw_data)
        if isinstance(summary, pd.DataFrame)
        else {}
    )
    overall = analysis.get("overall_severity")
    overview_severity = (
        overall.iloc[0].get("Benchmark Severity", "Unavailable")
        if isinstance(overall, pd.DataFrame) and not overall.empty
        else "Unavailable"
    )
    overview_year_range = (
        f"{min(validated_years)}&ndash;{max(validated_years)}"
        if validated_years
        else "Unavailable"
    )
    overview_validation = "Partial" if result.partial else "Approved"
    with st.container(key="analysis_overview", gap="medium"):
        st.markdown(
            f"""
            <div class="overview-summary">
                <div class="overview-summary-item">
                    <div class="overview-summary-label">Company</div>
                    <div class="overview-summary-value">{company_name} ({company_ticker})</div>
                </div>
                <div class="overview-summary-item">
                    <div class="overview-summary-label">Fiscal-year range</div>
                    <div class="overview-summary-value">{overview_year_range}</div>
                </div>
                <div class="overview-summary-item">
                    <div class="overview-summary-label">Validation status</div>
                    <div class="overview-summary-value">{overview_validation}</div>
                </div>
                <div class="overview-summary-item">
                    <div class="overview-summary-label">Overall severity</div>
                    <div class="overview-summary-value">{escape(str(overview_severity))}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="overview-section-label">Latest fiscal-year snapshot</div>',
            unsafe_allow_html=True,
        )
        _financial_kpi_cards(summary, analysis, raw_data)
        st.markdown(
            '<div class="overview-section-label">Financial trends</div>',
            unsafe_allow_html=True,
        )
        if isinstance(summary, pd.DataFrame):
            _financial_chart(summary, raw_data)
        st.markdown(
            '<div class="overview-section-label">Financial summary table</div>',
            unsafe_allow_html=True,
        )
        _section_summary(summary)
        _show_frame(
            summary,
            empty_message="No calculation summary is available.",
            monetary_units=summary_units,
        )

with tabs[2]:
    cash_conversion = calculations.get("cash_conversion")
    _section_heading(
        "Cash Conversion and Accrual Quality",
        "Compare revenue and earnings growth with the related receivables and operating-cash-flow trends.",
    )
    _section_status_snapshot(
        cash_conversion,
        columns=("Accrual Signal", "Severity"),
        label_overrides={"Accrual Signal": "Investor Review Status"},
    )
    _section_summary(cash_conversion)
    _analysis_chart(
        cash_conversion,
        columns=("Revenue Growth", "AR Growth", "Net Income Growth", "OCF Growth"),
        title="Growth trends: accruals and cash",
        y_title="Year-over-year growth",
        percentage=True,
    )
    _show_investor_results(
        cash_conversion,
        preferred_columns=(
            "Fiscal Year",
            "Revenue Growth",
            "AR Growth",
            "Net Income Growth",
            "OCF Growth",
            "Accrual Signal",
            "Severity",
            "Explanation",
        ),
        label_overrides={
            "AR Growth": "Customer Receivables Growth",
            "OCF Growth": "Operating Cash Flow Growth",
            "Accrual Signal": "Investor Review Status",
        },
        empty_message="No cash-conversion results are available.",
    )

with tabs[3]:
    working_capital = analysis.get("working_capital")
    working_capital_units = (
        _monetary_units_for_columns(working_capital.columns, raw_data)
        if isinstance(working_capital, pd.DataFrame)
        else {}
    )
    _section_heading(
        "Working Capital",
        "Track the reported operating-asset and payable movements alongside their calculated net cash effect.",
    )
    _section_status_snapshot(
        working_capital,
        columns=("WC Result", "Overall Severity"),
        label_overrides={"WC Result": "Cash Effect Status"},
    )
    _section_summary(working_capital)
    _analysis_chart(
        working_capital,
        columns=(
            "AR Change",
            "Inventory Change",
            "AP Change",
            "Net Working Capital Cash Effect",
        ),
        title="Working-capital movements",
        y_title="USD millions",
        bars=True,
        monetary_units=working_capital_units,
    )
    _show_investor_results(
        working_capital,
        preferred_columns=(
            "Fiscal Year",
            "Inventory Result",
            "Inventory Severity",
            "AP Result",
            "AP Severity",
            "WC Result",
            "WC Severity",
            "Overall Severity",
            "Explanation",
        ),
        label_overrides={
            "Inventory Result": "Inventory Status",
            "AP Result": "Supplier Payments Status",
            "AP Severity": "Supplier Payments Severity",
            "WC Result": "Cash Effect Status",
            "WC Severity": "Cash Effect Severity",
        },
        empty_message="No working-capital results are available.",
        monetary_units=working_capital_units,
    )

with tabs[4]:
    taxes = analysis.get("taxes")
    tax_units = (
        _monetary_units_for_columns(taxes.columns, raw_data)
        if isinstance(taxes, pd.DataFrame)
        else {}
    )
    _section_heading(
        "Deferred Taxes",
        "Review deferred tax assets and liabilities against net income and the existing tax-rule outputs.",
    )
    _section_status_snapshot(
        taxes,
        columns=("Deferred Tax Movement Result", "Overall Tax Severity"),
        label_overrides={"Deferred Tax Movement Result": "Balance Movement Status"},
    )
    _section_summary(taxes)
    _analysis_chart(
        taxes,
        columns=("Deferred Tax Assets", "Deferred Tax Liabilities", "Net Income"),
        title="Deferred-tax balances and net income",
        y_title="USD millions",
        monetary_units=tax_units,
    )
    _show_investor_results(
        taxes,
        preferred_columns=(
            "Fiscal Year",
            "Deferred Tax Assets",
            "Deferred Tax Liabilities",
            "DTA Result",
            "DTA Severity",
            "Deferred Tax Movement Result",
            "Deferred Tax Movement Severity",
            "Overall Tax Severity",
            "Explanation",
        ),
        label_overrides={
            "DTA Result": "Asset Recoverability Status",
            "DTA Severity": "Asset Recoverability Severity",
            "Deferred Tax Movement Result": "Balance Movement Status",
            "Deferred Tax Movement Severity": "Balance Movement Severity",
        },
        empty_message="No deferred-tax results are available.",
        monetary_units=tax_units,
    )

with tabs[5]:
    sbc = analysis.get("sbc")
    sbc_units = (
        _monetary_units_for_columns(sbc.columns, raw_data)
        if isinstance(sbc, pd.DataFrame)
        else {}
    )
    _section_heading(
        "Stock-Based Compensation and Dilution",
        "Compare stock-based compensation with net income while retaining the existing dilution and buyback assessments.",
    )
    _section_status_snapshot(
        sbc,
        columns=("Dilution Result", "Overall SBC Severity"),
        label_overrides={"Dilution Result": "Share Dilution Status"},
    )
    _section_summary(sbc)
    _analysis_chart(
        sbc,
        columns=("SBC", "Net Income"),
        title="Stock-based compensation and net income",
        y_title="USD millions",
        monetary_units=sbc_units,
    )
    _show_investor_results(
        sbc,
        preferred_columns=(
            "Fiscal Year",
            "SBC",
            "SBC / Net Income",
            "Large SBC Result",
            "Large SBC Severity",
            "Dilution Result",
            "Dilution Severity",
            "Buyback Offset Result",
            "Buyback Offset Severity",
            "Overall SBC Severity",
            "Explanation",
        ),
        label_overrides={
            "SBC": "Stock-Based Compensation",
            "Large SBC Result": "Compensation Level Status",
            "Large SBC Severity": "Compensation Level Severity",
            "Dilution Result": "Share Dilution Status",
            "Buyback Offset Result": "Buyback Offset Status",
        },
        empty_message="No SBC results are available.",
        monetary_units=sbc_units,
    )

with tabs[6]:
    normalized_earnings = calculations.get("normalized_earnings")
    normalized_units = (
        _monetary_units_for_columns(normalized_earnings.columns, raw_data)
        if isinstance(normalized_earnings, pd.DataFrame)
        else {}
    )
    _section_heading(
        "Normalized Earnings",
        "Compare reported and normalized net income with the existing one-off and normalization rule results.",
    )
    _section_status_snapshot(
        normalized_earnings,
        columns=("Large Normalization Difference Result", "Overall Severity"),
        label_overrides={
            "Large Normalization Difference Result": "Adjustment Size Status"
        },
    )
    _section_summary(normalized_earnings)
    _analysis_chart(
        normalized_earnings,
        columns=("Reported Net Income", "Normalized Net Income"),
        title="Reported versus normalized earnings",
        y_title="USD millions",
        monetary_units=normalized_units,
    )
    _show_investor_results(
        normalized_earnings,
        preferred_columns=(
            "Fiscal Year",
            "Reported Net Income",
            "Normalized Net Income",
            "Percentage Difference",
            "Large Normalization Difference Result",
            "Large Normalization Difference Severity",
            "Repeated One-Off Result",
            "Repeated One-Off Severity",
            "Overall Severity",
            "Explanation",
        ),
        label_overrides={
            "Percentage Difference": "Earnings Adjustment Difference",
            "Large Normalization Difference Result": "Adjustment Size Status",
            "Large Normalization Difference Severity": "Adjustment Size Severity",
            "Repeated One-Off Result": "Repeated Adjustments Status",
            "Repeated One-Off Severity": "Repeated Adjustments Severity",
        },
        empty_message="Normalized-earnings evidence is unavailable.",
        monetary_units=normalized_units,
    )

with tabs[7]:
    _section_heading(
        "Red Flags and Existing Severities",
        "The presentation below reflects the pipeline's existing flags and severity classifications without reclassification.",
    )
    _severity_cards(analysis)
    st.caption(
        "Status and severity labels below are the exact pipeline outputs; descriptions are presented in investor-readable language."
    )
    st.markdown(
        '<div class="red-flag-table-heading">Human-readable red-flag results</div>',
        unsafe_allow_html=True,
    )
    _show_frame(
        _humanized_red_flag_frame(analysis),
        empty_message="No red-flag results are available.",
    )
    with st.expander(
        "Exact rules, formulas, thresholds, and source results", type="compact"
    ):
        st.caption(
            "This audit view preserves every underlying rule, calculation, threshold, result, flag, severity, and explanation without rewriting."
        )
        _show_frame(
            analysis.get("red_flags"),
            empty_message="No exact red-flag methodology is available.",
            height=520,
        )
    with st.expander(
        "Exact severity details and fiscal-year summaries", type="compact"
    ):
        _show_frame(
            analysis.get("detailed_severity"),
            empty_message="No detailed severity results are available.",
        )
        _show_frame(
            analysis.get("fiscal_year_severity"),
            empty_message="No fiscal-year severity summary is available.",
        )

with tabs[8]:
    _section_heading(
        "Investor-Focused Interpretations",
        "Company-specific narrative outputs generated from the validated analysis package.",
    )
    if isinstance(result.interpretations, Mapping) and result.interpretations:
        _render_interpretations(result.interpretations)
    else:
        st.info("No interpretation output is available.")

    excel_path = downloadable_workbook_path(
        result, selected_company, selected_analysis_years
    )
    if excel_path is not None:
        st.divider()
        st.download_button(
            "Download Generated Excel Report",
            data=excel_path.read_bytes(),
            file_name=excel_path.name,
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            width="stretch",
        )
    elif result.excel_output:
        st.warning(
            "A valid final workbook is not available for the current company "
            "and fiscal-year selection."
        )
