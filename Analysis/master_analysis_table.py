import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Import the validated task outputs without replaying each task's console report.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.accrual_red_flags import accrual_red_flags_df
    from Analysis.capex_rule import capex_rule_df
    from Analysis.dta_analysis import dta_analysis_df
    from Analysis.dtl_analysis import dtl_analysis_df
    from Analysis.normalization_red_flags import normalization_red_flags_df
    from Analysis.sbc_red_flags import sbc_red_flags_df
    from Analysis.severity_system import fiscal_year_severity_summary_df
    from Analysis.tax_red_flags import tax_red_flags_df
    from Analysis.working_capital_red_flags import working_capital_red_flags_df
    from Calculations.capex_analysis import capex_analysis_df
    from Calculations.da_analysis import da_analysis_df
    from Calculations.free_cash_flow import free_cash_flow_df
    from Calculations.net_income_growth import net_income_growth_df
    from Calculations.ocf_growth import ocf_growth_df
    from Calculations.revenue_growth import revenue_growth_df
    from Calculations.sbc_analysis import sbc_analysis_df
    from Calculations.share_dilution import share_dilution_df
    from Data.apple_test_dataset import apple_financial_data_df, verified_values


REQUIRED_YEARS = [2022, 2023, 2024, 2025]
CORE_METRICS = [
    "Revenue", "Net Income", "Operating Cash Flow", "Capital Expenditures",
    "Accounts Receivable", "Inventory", "Accounts Payable",
    "Depreciation & Amortization", "Stock-Based Compensation",
    "Shares Outstanding", "Deferred Tax Assets", "Deferred Tax Liabilities",
    "Tax Expense",
]


def selected(frame, columns, rename=None):
    """Return only consolidation fields, with one row per fiscal year."""
    result = frame[columns].copy()
    if rename:
        result = result.rename(columns=rename)
    if result["Fiscal Year"].duplicated().any():
        raise ValueError("A source table contains duplicated fiscal years")
    return result


master_analysis_df = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"].isin(CORE_METRICS),
        ["Fiscal Year", "Metric", "Value"],
    ]
    .pivot(index="Fiscal Year", columns="Metric", values="Value")
    .reindex(REQUIRED_YEARS)
    .reset_index()
    .rename_axis(columns=None)
)

sources = [
    selected(free_cash_flow_df, ["Fiscal Year", "Free Cash Flow"]),
    selected(revenue_growth_df, ["Fiscal Year", "Result"], {"Result": "Revenue Growth"}),
    selected(net_income_growth_df, ["Fiscal Year", "NI Growth Result"], {"NI Growth Result": "Net Income Growth"}),
    selected(ocf_growth_df, ["Fiscal Year", "OCF Growth Result"], {"OCF Growth Result": "OCF Growth"}),
    selected(da_analysis_df, ["Fiscal Year", "D&A Growth", "D&A / Revenue"]),
    selected(capex_analysis_df, ["Fiscal Year", "CapEx Growth", "CapEx / Revenue", "CapEx / D&A"]),
    selected(capex_rule_df, ["Fiscal Year", "Status"], {"Status": "CapEx Investigation Result"}),
    selected(sbc_analysis_df, ["Fiscal Year", "SBC Growth", "SBC / Revenue", "SBC / OCF", "SBC / Net Income"]),
    selected(share_dilution_df, ["Fiscal Year", "Shares Outstanding Growth"]),
    selected(
        accrual_red_flags_df,
        ["Fiscal Year", "AR Growth", "AR Revenue Gap", "AR Flag", "NI OCF Flag", "Combined Accrual Flag", "Accrual Signal", "Severity"],
        {"Severity": "Accrual Severity"},
    ),
    selected(
        working_capital_red_flags_df,
        ["Fiscal Year", "Inventory Growth", "AP Growth", "AR Change", "Inventory Change", "AP Change", "Net Working Capital Cash Effect", "Working Capital Cash Use", "Inventory Flag", "Inventory Severity", "AP Classification", "AP Result", "AP Severity", "Working Capital Signal", "Overall Severity"],
        {"Overall Severity": "Working Capital Severity"},
    ),
    selected(
        sbc_red_flags_df,
        ["Fiscal Year", "Large SBC Flag", "Dilution Flag", "Shares Issued Net", "Shares Repurchased", "Net Share Effect", "Buyback Offset Ratio", "Cash Spent on Buybacks", "Buyback Offset Classification", "SBC Signal", "Overall SBC Severity"],
        {"Overall SBC Severity": "SBC Severity"},
    ),
    selected(
        dta_analysis_df,
        ["Fiscal Year", "DTA / Net Income", "DTA Growth", "Status"],
        {"Status": "DTA Risk Result"},
    ),
    selected(dtl_analysis_df, ["Fiscal Year", "DTL Growth"]),
    selected(
        tax_red_flags_df,
        ["Fiscal Year", "DTA Risk Flag", "Deferred Tax Movement Flag", "Deferred Tax Movement Classification", "Tax Signal", "Overall Tax Severity"],
        {"Overall Tax Severity": "Tax Severity"},
    ),
    selected(
        normalization_red_flags_df,
        ["Fiscal Year", "Reported Net Income", "Normalized Net Income", "Difference", "Percentage Difference", "Earnings Adjustment Direction", "One-Off Categories Identified", "Repeated One-Off Flag", "Large Normalization Difference Flag", "Normalization Signal", "Overall Severity"],
        {"Difference": "Normalization Difference", "Percentage Difference": "Normalization Difference Percentage", "Overall Severity": "Normalization Severity"},
    ),
    selected(
        fiscal_year_severity_summary_df,
        ["Fiscal Year", "Triggered Metrics", "Material Concern Count", "Needs Investigation Count", "Low Risk Count", "High-Level Severity"],
    ),
]

for source in sources:
    master_analysis_df = master_analysis_df.merge(source, on="Fiscal Year", how="left", validate="one_to_one")

# Calculation fields must remain numeric. Missing prior-year values therefore
# stay as numeric NaN rather than becoming presentation strings.
NUMERIC_CALCULATION_COLUMNS = [
    "Revenue Growth", "AR Growth", "Inventory Growth", "AP Growth",
    "Net Income Growth", "OCF Growth", "D&A Growth", "CapEx Growth",
    "SBC Growth", "Shares Outstanding Growth", "AR Revenue Gap",
    "DTA Growth", "DTL Growth", "AR Change", "Inventory Change",
    "AP Change", "Net Working Capital Cash Effect", "D&A / Revenue",
    "CapEx / Revenue", "CapEx / D&A", "SBC / Revenue", "SBC / OCF",
    "SBC / Net Income", "DTA / Net Income", "Shares Issued Net",
    "Shares Repurchased", "Net Share Effect", "Buyback Offset Ratio",
    "Cash Spent on Buybacks", "Reported Net Income",
    "Normalized Net Income", "Normalization Difference",
    "Normalization Difference Percentage", "Free Cash Flow",
]
for column in NUMERIC_CALCULATION_COLUMNS:
    master_analysis_df[column] = pd.to_numeric(
        master_analysis_df[column], errors="coerce"
    )

# Task 35 and Task 36 assess 2023 onward. Preserve that boundary explicitly.
flag_not_available = [
    "AR Flag", "NI OCF Flag", "Combined Accrual Flag", "Inventory Flag",
    "Deferred Tax Movement Flag",
]
categorical_not_available = [
    "Accrual Signal", "Accrual Severity", "Inventory Severity",
    "AP Classification", "AP Result", "AP Severity", "Working Capital Signal",
    "Working Capital Severity",
    "Deferred Tax Movement Classification", "Tax Signal", "Tax Severity",
]
master_analysis_df.loc[master_analysis_df["Fiscal Year"] == 2022, flag_not_available] = pd.NA
master_analysis_df.loc[master_analysis_df["Fiscal Year"] == 2022, categorical_not_available] = "N/A"
# Task 19 does assess DTA risk in 2022; expose its existing result as a Boolean.
master_analysis_df.loc[master_analysis_df["Fiscal Year"] == 2022, "DTA Risk Flag"] = (
    master_analysis_df.loc[master_analysis_df["Fiscal Year"] == 2022, "DTA Risk Result"]
    .ne("No investigation triggered")
)
for column in flag_not_available + ["DTA Risk Flag"]:
    master_analysis_df[column] = master_analysis_df[column].astype("boolean")
master_analysis_df.loc[master_analysis_df["Fiscal Year"] == 2022, "Triggered Metrics"] = "N/A"
master_analysis_df.loc[master_analysis_df["Fiscal Year"] == 2022, "High-Level Severity"] = "Not Assessed"

# Helpful display fields accompany, but never replace, raw decimal calculations.
for column in [
    "Revenue Growth", "AR Growth", "Inventory Growth", "AP Growth",
    "Net Income Growth", "OCF Growth", "D&A Growth", "CapEx Growth",
    "SBC Growth", "Shares Outstanding Growth",
]:
    master_analysis_df[f"{column} Display"] = master_analysis_df[column].map(
        lambda value: "N/A" if pd.isna(value) else f"{value:.2%}"
    )

analyst_summary_columns = [
    "Fiscal Year", "Revenue", "Net Income", "Operating Cash Flow",
    "Free Cash Flow", "AR Revenue Gap", "Net Working Capital Cash Effect",
    "SBC / Net Income", "DTA / Net Income", "Normalized Net Income",
    "Normalization Difference Percentage", "Accrual Severity",
    "Working Capital Severity", "SBC Severity", "Tax Severity",
    "Normalization Severity", "High-Level Severity",
]
analyst_summary_df = master_analysis_df[analyst_summary_columns].rename(
    columns={"Operating Cash Flow": "OCF"}
)


validation_errors = []
if len(master_analysis_df) != 4 or master_analysis_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("The master table must contain exactly fiscal years 2022-2025")
if master_analysis_df["Fiscal Year"].duplicated().any():
    validation_errors.append("The master table contains duplicated fiscal years")

core_by_year = master_analysis_df.set_index("Fiscal Year")
for year in REQUIRED_YEARS:
    for metric in CORE_METRICS:
        if core_by_year.loc[year, metric] != verified_values[year][metric]:
            validation_errors.append(f"Core benchmark mismatch: {year} {metric}")

checks = [
    (free_cash_flow_df, ["Free Cash Flow"], None),
    (working_capital_red_flags_df, ["AR Change", "Inventory Change", "AP Change", "Net Working Capital Cash Effect"], None),
    (accrual_red_flags_df, ["AR Revenue Gap", "AR Flag", "NI OCF Flag", "Combined Accrual Flag", "Accrual Signal"], None),
    (sbc_red_flags_df, ["SBC / Net Income", "Large SBC Flag", "Dilution Flag", "SBC Signal"], None),
    (normalization_red_flags_df, ["Reported Net Income", "Normalized Net Income", "Repeated One-Off Flag", "Large Normalization Difference Flag", "Normalization Signal"], None),
    (tax_red_flags_df, ["DTA Risk Flag", "Deferred Tax Movement Flag", "Tax Signal"], None),
    (fiscal_year_severity_summary_df, ["High-Level Severity"], None),
]
for frame, columns, _ in checks:
    expected = frame.set_index("Fiscal Year")[columns].sort_index()
    actual = master_analysis_df.set_index("Fiscal Year").loc[expected.index, columns].sort_index()
    try:
        pd.testing.assert_frame_equal(
            actual, expected, check_dtype=False, check_names=False
        )
    except AssertionError:
        validation_errors.append(f"Source results were not preserved for {columns}")

expected_wc = {2023: -4213, 2024: 1492, 2025: -3899}
if core_by_year.loc[list(expected_wc), "Net Working Capital Cash Effect"].to_dict() != expected_wc:
    validation_errors.append("Working-capital benchmark values do not match Task 14")
if core_by_year.loc[2022, "High-Level Severity"] != "Not Assessed":
    validation_errors.append("2022 High-Level Severity must be Not Assessed")
if not pd.isna(core_by_year.loc[2022, "Revenue Growth"]):
    validation_errors.append("Unavailable 2022 growth must remain NaN")

required_numeric_columns = [
    "Revenue Growth", "AR Growth", "Inventory Growth", "AP Growth",
    "Net Income Growth", "OCF Growth", "D&A Growth", "CapEx Growth",
    "SBC Growth", "Shares Outstanding Growth", "AR Revenue Gap",
    "Net Working Capital Cash Effect",
]
non_numeric_columns = [
    column
    for column in required_numeric_columns
    if not pd.api.types.is_numeric_dtype(master_analysis_df[column])
]
if non_numeric_columns:
    validation_errors.append(
        f"Calculation columns must have numeric dtype: {non_numeric_columns}"
    )

prior_year_numeric_columns = [
    "Revenue Growth", "AR Growth", "Inventory Growth", "AP Growth",
    "Net Income Growth", "OCF Growth", "D&A Growth", "CapEx Growth",
    "SBC Growth", "Shares Outstanding Growth", "AR Revenue Gap",
    "DTA Growth", "DTL Growth", "AR Change", "Inventory Change",
    "AP Change", "Net Working Capital Cash Effect",
]
if not core_by_year.loc[2022, prior_year_numeric_columns].isna().all():
    validation_errors.append(
        "Unavailable 2022 prior-year numerical values must remain NaN"
    )

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 240)
print("Master analysis table:")
print(master_analysis_df.to_string(index=False, na_rep="NaN"))
print("\nAnalyst summary:")
print(analyst_summary_df.to_string(index=False, na_rep="NaN"))

if validation_errors:
    raise ValueError("Master analysis table validation failed:\n- " + "\n- ".join(validation_errors))
print("\nMaster analysis table validated successfully")
