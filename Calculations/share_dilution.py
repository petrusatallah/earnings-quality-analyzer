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
zero_tolerance = 1e-12

share_dilution_df = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"] == "Shares Outstanding",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")
    .reindex(required_years)
    .rename(columns={"Value": "Shares Outstanding"})
    .reset_index()
)

share_dilution_df["Previous Year Shares Outstanding"] = share_dilution_df[
    "Shares Outstanding"
].shift(1)
share_dilution_df["Shares Outstanding Growth"] = (
    share_dilution_df["Shares Outstanding"]
    - share_dilution_df["Previous Year Shares Outstanding"]
) / share_dilution_df["Previous Year Shares Outstanding"]
share_dilution_df["Shares Outstanding Growth Percentage"] = share_dilution_df[
    "Shares Outstanding Growth"
].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2%}")


def classify_direction(growth):
    if pd.isna(growth):
        return "N/A"
    if abs(growth) <= zero_tolerance:
        return "No change"
    if growth > 0:
        return "Dilution / share count increase"
    return "Share count decrease"


share_dilution_df["Direction"] = share_dilution_df[
    "Shares Outstanding Growth"
].map(classify_direction)

share_dilution_df = share_dilution_df[
    [
        "Fiscal Year",
        "Shares Outstanding",
        "Previous Year Shares Outstanding",
        "Shares Outstanding Growth",
        "Shares Outstanding Growth Percentage",
        "Direction",
    ]
]

print(share_dilution_df.to_string(index=False, na_rep="N/A"))

expected_shares = [15943.425, 15550.061, 15116.786, 14773.260]
expected_growth = [None, -0.0247, -0.0279, -0.0227]
expected_directions = [
    "N/A",
    "Share count decrease",
    "Share count decrease",
    "Share count decrease",
]
validation_tolerance = 0.0001

validation_passed = (
    len(share_dilution_df) == 4
    and share_dilution_df["Fiscal Year"].tolist() == required_years
    and all(
        abs(actual - expected) <= validation_tolerance
        for actual, expected in zip(
            share_dilution_df["Shares Outstanding"], expected_shares
        )
    )
    and pd.isna(
        share_dilution_df.loc[0, "Previous Year Shares Outstanding"]
    )
    and pd.isna(share_dilution_df.loc[0, "Shares Outstanding Growth"])
    and all(
        abs(actual - expected) <= validation_tolerance
        for actual, expected in zip(
            share_dilution_df.loc[1:, "Shares Outstanding Growth"],
            expected_growth[1:],
        )
    )
    and share_dilution_df["Direction"].tolist() == expected_directions
)

if validation_passed:
    print("Share dilution calculations validated successfully")
else:
    print("Share dilution calculations validation failed")
