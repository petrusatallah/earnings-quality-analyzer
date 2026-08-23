import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress output produced by the existing data and calculation modules during
# import so this module prints only the DTA analysis.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.net_income_growth import net_income_growth_df
    from Data.apple_test_dataset import apple_financial_data_df
    from Data.deferred_tax_data import deferred_tax_data_df


required_years = [2022, 2023, 2024, 2025]
exact_rule = (
    "DTA / |Net Income| >= 50% AND "
    "(NI Growth <= -10% OR Net Income <= 0)"
)

dta_by_year = (
    deferred_tax_data_df.loc[
        deferred_tax_data_df["Metric"] == "Deferred Tax Assets",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

net_income_by_year = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"] == "Net Income",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

ni_growth_by_year = net_income_growth_df.set_index("Fiscal Year")[
    "NI Growth Result"
]

calculation_records = []

for fiscal_year in required_years:
    dta = dta_by_year.loc[fiscal_year]
    net_income = net_income_by_year.loc[fiscal_year]

    if fiscal_year == required_years[0]:
        dta_growth = None
        ni_growth = None
    else:
        previous_dta = dta_by_year.loc[fiscal_year - 1]
        dta_growth = (dta - previous_dta) / previous_dta
        ni_growth = ni_growth_by_year.loc[fiscal_year]

    # For positive profitability this is DTA / Net Income. For negative
    # profitability, magnitude is evaluated using abs(Net Income). A zero
    # denominator is not mathematically defined.
    dta_to_net_income = None if net_income == 0 else dta / abs(net_income)

    large_dta = (
        dta_to_net_income is not None and dta_to_net_income >= 0.50
    )
    weak_profitability_trend = (
        ni_growth is not None and ni_growth <= -0.10
    )
    negative_profitability = net_income <= 0

    needs_investigation = large_dta and (
        weak_profitability_trend or negative_profitability
    )
    status = (
        "Needs investigation"
        if needs_investigation
        else "No investigation triggered"
    )

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "DTA": dta,
            "DTA Growth": dta_growth,
            "DTA Growth Percentage": (
                "N/A" if dta_growth is None else f"{dta_growth:.2%}"
            ),
            "Net Income": net_income,
            "Net Income Growth": ni_growth,
            "Net Income Growth Percentage": (
                "N/A" if ni_growth is None else f"{ni_growth:.2%}"
            ),
            "DTA / Net Income": dta_to_net_income,
            "DTA / Net Income Percentage": (
                "N/A"
                if dta_to_net_income is None
                else f"{dta_to_net_income:.2%}"
            ),
            "Large DTA": large_dta,
            "Weak Profitability Trend": weak_profitability_trend,
            "Negative Profitability": negative_profitability,
            "Taxable Income Data": "Not available",
            "Exact Rule": exact_rule,
            "Status": status,
        }
    )

dta_analysis_df = pd.DataFrame(calculation_records)

print(dta_analysis_df.to_string(index=False))

expected_statuses = {
    2022: "No investigation triggered",
    2023: "No investigation triggered",
    2024: "No investigation triggered",
    2025: "No investigation triggered",
}

validation_passed = (
    len(dta_analysis_df) == 4
    and dta_analysis_df["Fiscal Year"].tolist() == required_years
    and pd.isna(dta_analysis_df.loc[0, "DTA Growth"])
    and pd.isna(dta_analysis_df.loc[0, "Net Income Growth"])
    and (dta_analysis_df["Taxable Income Data"] == "Not available").all()
    and (dta_analysis_df["Exact Rule"] == exact_rule).all()
    and all(
        row["Status"] == expected_statuses[row["Fiscal Year"]]
        for _, row in dta_analysis_df.iterrows()
    )
)

if validation_passed:
    print("DTA analysis validated successfully")
else:
    print("DTA analysis validation failed")
