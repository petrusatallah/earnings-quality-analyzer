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
    "Stock-Based Compensation",
    "Revenue",
    "Operating Cash Flow",
    "Net Income",
]

sbc_analysis_df = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"].isin(required_metrics),
        ["Fiscal Year", "Metric", "Value"],
    ]
    .pivot(index="Fiscal Year", columns="Metric", values="Value")
    .reindex(required_years)
    .rename(
        columns={
            "Stock-Based Compensation": "SBC",
            "Operating Cash Flow": "OCF",
        }
    )
    .reset_index()
)

sbc_analysis_df["SBC Growth"] = sbc_analysis_df["SBC"].pct_change(
    fill_method=None
)
sbc_analysis_df["SBC Growth Percentage"] = sbc_analysis_df["SBC Growth"].map(
    lambda value: "N/A" if pd.isna(value) else f"{value:.2%}"
)

for denominator in ["Revenue", "OCF", "Net Income"]:
    ratio_column = f"SBC / {denominator}"
    sbc_analysis_df[ratio_column] = (
        sbc_analysis_df["SBC"] / sbc_analysis_df[denominator]
    )
    sbc_analysis_df[f"{ratio_column} Percentage"] = sbc_analysis_df[
        ratio_column
    ].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2%}")

sbc_analysis_df = sbc_analysis_df[
    [
        "Fiscal Year",
        "SBC",
        "Revenue",
        "OCF",
        "Net Income",
        "SBC Growth",
        "SBC Growth Percentage",
        "SBC / Revenue",
        "SBC / Revenue Percentage",
        "SBC / OCF",
        "SBC / OCF Percentage",
        "SBC / Net Income",
        "SBC / Net Income Percentage",
    ]
]

print(sbc_analysis_df.to_string(index=False, na_rep="N/A"))

expected_sbc = [9038, 10833, 11688, 12863]
expected_growth = [None, 0.1986, 0.0789, 0.1005]
expected_revenue_ratios = [0.0229, 0.0283, 0.0299, 0.0309]
expected_ocf_ratios = [0.0740, 0.0980, 0.0988, 0.1154]
expected_net_income_ratios = [0.0906, 0.1117, 0.1247, 0.1148]
tolerance = 0.0001

validation_passed = (
    len(sbc_analysis_df) == 4
    and sbc_analysis_df["Fiscal Year"].tolist() == required_years
    and sbc_analysis_df["SBC"].tolist() == expected_sbc
    and not sbc_analysis_df[["SBC", "Revenue", "OCF", "Net Income"]]
    .isna()
    .any()
    .any()
    and pd.isna(sbc_analysis_df.loc[0, "SBC Growth"])
    and all(
        abs(actual - expected) <= tolerance
        for actual, expected in zip(
            sbc_analysis_df.loc[1:, "SBC Growth"], expected_growth[1:]
        )
    )
    and all(
        abs(actual - expected) <= tolerance
        for actual, expected in zip(
            sbc_analysis_df["SBC / Revenue"], expected_revenue_ratios
        )
    )
    and all(
        abs(actual - expected) <= tolerance
        for actual, expected in zip(
            sbc_analysis_df["SBC / OCF"], expected_ocf_ratios
        )
    )
    and all(
        abs(actual - expected) <= tolerance
        for actual, expected in zip(
            sbc_analysis_df["SBC / Net Income"],
            expected_net_income_ratios,
        )
    )
)

if validation_passed:
    print("SBC analysis validated successfully")
else:
    print("SBC analysis validation failed")
