import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress verification output produced by the dataset during import.
with contextlib.redirect_stdout(io.StringIO()):
    from Data.apple_test_dataset import apple_financial_data_df


required_years = [2022, 2023, 2024, 2025]
required_metrics = [
    "Capital Expenditures",
    "Revenue",
    "Depreciation & Amortization",
]

capex_analysis_df = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"].isin(required_metrics),
        ["Fiscal Year", "Metric", "Value"],
    ]
    .pivot(index="Fiscal Year", columns="Metric", values="Value")
    .reindex(required_years)
    .rename(
        columns={
            "Capital Expenditures": "CapEx",
            "Depreciation & Amortization": "D&A",
        }
    )
    .reset_index()
)

capex_analysis_df["CapEx Growth"] = capex_analysis_df["CapEx"].pct_change(
    fill_method=None
)
capex_analysis_df["CapEx Growth Percentage"] = capex_analysis_df[
    "CapEx Growth"
].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2%}")

capex_analysis_df["CapEx / Revenue"] = (
    capex_analysis_df["CapEx"] / capex_analysis_df["Revenue"]
)
capex_analysis_df["CapEx / Revenue Percentage"] = capex_analysis_df[
    "CapEx / Revenue"
].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2%}")

capex_analysis_df["CapEx / D&A"] = (
    capex_analysis_df["CapEx"] / capex_analysis_df["D&A"]
)
capex_analysis_df["CapEx / D&A Display"] = capex_analysis_df[
    "CapEx / D&A"
].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2f}x")

capex_analysis_df = capex_analysis_df[
    [
        "Fiscal Year",
        "CapEx",
        "Revenue",
        "D&A",
        "CapEx Growth",
        "CapEx Growth Percentage",
        "CapEx / Revenue",
        "CapEx / Revenue Percentage",
        "CapEx / D&A",
        "CapEx / D&A Display",
    ]
]

print(capex_analysis_df.to_string(index=False, na_rep="N/A"))

validation_passed = (
    len(capex_analysis_df) == 4
    and capex_analysis_df["Fiscal Year"].tolist() == required_years
    and not capex_analysis_df[["CapEx", "Revenue", "D&A"]].isna().any().any()
    and not capex_analysis_df["CapEx / Revenue"].isna().any()
    and not capex_analysis_df["CapEx / D&A"].isna().any()
    and capex_analysis_df.loc[
        capex_analysis_df["Fiscal Year"].isin([2023, 2024, 2025]),
        "CapEx Growth",
    ].notna().all()
    and pd.isna(
        capex_analysis_df.loc[
            capex_analysis_df["Fiscal Year"] == 2022, "CapEx Growth"
        ].iloc[0]
    )
)

if validation_passed:
    print("CapEx calculations validated successfully")
else:
    print("CapEx calculations validation failed")
