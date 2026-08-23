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
required_metrics = ["Depreciation & Amortization", "Revenue"]

da_analysis_df = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"].isin(required_metrics),
        ["Fiscal Year", "Metric", "Value"],
    ]
    .pivot(index="Fiscal Year", columns="Metric", values="Value")
    .reindex(required_years)
    .rename(columns={"Depreciation & Amortization": "D&A"})
    .reset_index()
)

da_analysis_df["D&A Growth"] = da_analysis_df["D&A"].pct_change(fill_method=None)
da_analysis_df["D&A Growth Percentage"] = da_analysis_df["D&A Growth"].map(
    lambda value: "N/A" if pd.isna(value) else f"{value:.2%}"
)
da_analysis_df["D&A / Revenue"] = (
    da_analysis_df["D&A"] / da_analysis_df["Revenue"]
)
da_analysis_df["D&A / Revenue Percentage"] = da_analysis_df[
    "D&A / Revenue"
].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2%}")

da_analysis_df = da_analysis_df[
    [
        "Fiscal Year",
        "D&A",
        "Revenue",
        "D&A Growth",
        "D&A Growth Percentage",
        "D&A / Revenue",
        "D&A / Revenue Percentage",
    ]
]

print(da_analysis_df.to_string(index=False, na_rep="N/A"))

validation_passed = (
    len(da_analysis_df) == 4
    and da_analysis_df["Fiscal Year"].tolist() == required_years
    and not da_analysis_df[["D&A", "Revenue"]].isna().any().any()
    and not da_analysis_df["D&A / Revenue"].isna().any()
    and da_analysis_df.loc[
        da_analysis_df["Fiscal Year"].isin([2023, 2024, 2025]), "D&A Growth"
    ].notna().all()
    and pd.isna(
        da_analysis_df.loc[
            da_analysis_df["Fiscal Year"] == 2022, "D&A Growth"
        ].iloc[0]
    )
)

if validation_passed:
    print("D&A calculations validated successfully")
else:
    print("D&A calculations validation failed")
