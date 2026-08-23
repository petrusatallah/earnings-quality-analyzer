import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress table and validation output produced by the calculation modules.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.sbc_analysis import sbc_analysis_df
    from Calculations.share_dilution import share_dilution_df


required_years = [2022, 2023, 2024, 2025]
significant_dilution_threshold = 0.01

sbc_results = sbc_analysis_df[
    ["Fiscal Year", "SBC", "SBC Growth", "SBC Growth Percentage"]
]
share_results = share_dilution_df[
    [
        "Fiscal Year",
        "Shares Outstanding",
        "Shares Outstanding Growth",
        "Shares Outstanding Growth Percentage",
    ]
]

sbc_vs_dilution_df = (
    sbc_results.merge(share_results, on="Fiscal Year", how="inner")
    .set_index("Fiscal Year")
    .reindex(required_years)
    .reset_index()
)


def classify_year(row):
    sbc_growth = row["SBC Growth"]
    shares_growth = row["Shares Outstanding Growth"]

    if pd.isna(sbc_growth) or pd.isna(shares_growth):
        return pd.Series(
            [False, "N/A", False, "Insufficient prior-year data"]
        )

    if shares_growth >= significant_dilution_threshold:
        if sbc_growth > 0:
            return pd.Series(
                [
                    True,
                    "Shares Outstanding Growth >= 1% AND SBC Growth > 0",
                    True,
                    "Significant dilution; SBC also increased",
                ]
            )
        return pd.Series(
            [
                True,
                "Shares Outstanding Growth >= 1%",
                True,
                "Significant dilution",
            ]
        )

    return pd.Series(
        [
            False,
            "Shares Outstanding Growth < 1%",
            False,
            "No significant dilution",
        ]
    )


sbc_vs_dilution_df[
    ["Significant Dilution", "Exact Rule", "Flag", "Classification"]
] = sbc_vs_dilution_df.apply(classify_year, axis=1)

sbc_vs_dilution_df = sbc_vs_dilution_df[
    [
        "Fiscal Year",
        "SBC",
        "SBC Growth",
        "SBC Growth Percentage",
        "Shares Outstanding",
        "Shares Outstanding Growth",
        "Shares Outstanding Growth Percentage",
        "Significant Dilution",
        "Exact Rule",
        "Flag",
        "Classification",
    ]
]

print(sbc_vs_dilution_df.to_string(index=False, na_rep="N/A"))

expected_sbc_growth = [None, 0.1986, 0.0789, 0.1005]
expected_share_growth = [None, -0.0247, -0.0279, -0.0227]
expected_classifications = [
    "Insufficient prior-year data",
    "No significant dilution",
    "No significant dilution",
    "No significant dilution",
]
validation_tolerance = 0.0001

validation_passed = (
    len(sbc_vs_dilution_df) == 4
    and sbc_vs_dilution_df["Fiscal Year"].tolist() == required_years
    and pd.isna(sbc_vs_dilution_df.loc[0, "SBC Growth"])
    and pd.isna(sbc_vs_dilution_df.loc[0, "Shares Outstanding Growth"])
    and all(
        abs(actual - expected) <= validation_tolerance
        for actual, expected in zip(
            sbc_vs_dilution_df.loc[1:, "SBC Growth"],
            expected_sbc_growth[1:],
        )
    )
    and all(
        abs(actual - expected) <= validation_tolerance
        for actual, expected in zip(
            sbc_vs_dilution_df.loc[1:, "Shares Outstanding Growth"],
            expected_share_growth[1:],
        )
    )
    and not sbc_vs_dilution_df["Significant Dilution"].any()
    and not sbc_vs_dilution_df["Flag"].any()
    and sbc_vs_dilution_df["Classification"].tolist()
    == expected_classifications
)

if validation_passed:
    print("SBC versus dilution analysis validated successfully")
else:
    print("SBC versus dilution analysis validation failed")
