import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress table and validation output produced by the calculation module.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.share_dilution import share_dilution_df


required_years = [2022, 2023, 2024, 2025]
zero_tolerance = 1e-12

# Verified Apple Form 10-K source inputs for Task 24. Share values and cash
# amounts are in millions.
buyback_source_df = pd.DataFrame(
    {
        "Fiscal Year": required_years,
        "Shares Repurchased": [568.589, 471.419, 499.372, 401.672],
        "Shares Issued Net": [85.228, 78.055, 66.097, 58.146],
        "Cash Spent on Buybacks": [89402, 77550, 94949, 90711],
    }
)

share_growth_results = share_dilution_df[
    [
        "Fiscal Year",
        "Shares Outstanding Growth",
        "Shares Outstanding Growth Percentage",
    ]
]

buyback_adjustment_df = buyback_source_df.merge(
    share_growth_results, on="Fiscal Year", how="left"
)

buyback_adjustment_df["Net Share Effect"] = (
    buyback_adjustment_df["Shares Issued Net"]
    - buyback_adjustment_df["Shares Repurchased"]
)


def classify_net_share_effect(value):
    if abs(value) <= zero_tolerance:
        return "No net share change"
    if value < 0:
        return "Net share reduction"
    return "Net share increase"


buyback_adjustment_df["Net Share Effect Direction"] = buyback_adjustment_df[
    "Net Share Effect"
].map(classify_net_share_effect)

buyback_adjustment_df["Buyback Offset Ratio"] = (
    buyback_adjustment_df["Shares Repurchased"]
    / buyback_adjustment_df["Shares Issued Net"].where(
        buyback_adjustment_df["Shares Issued Net"].abs() > zero_tolerance
    )
)
buyback_adjustment_df["Buyback Offset Ratio Display"] = buyback_adjustment_df[
    "Buyback Offset Ratio"
].map(lambda value: "N/A" if pd.isna(value) else f"{value:.2f}x")
buyback_adjustment_df["Buyback Offset Classification"] = buyback_adjustment_df[
    "Buyback Offset Ratio"
].map(
    lambda value: (
        "N/A"
        if pd.isna(value)
        else (
            "Buybacks more than offset share issuance"
            if value >= 1.0
            else "Buybacks did not fully offset share issuance"
        )
    )
)
buyback_adjustment_df["Cash Spent Display"] = buyback_adjustment_df[
    "Cash Spent on Buybacks"
].map(lambda value: f"${value / 1000:.3f}B")

buyback_adjustment_df = buyback_adjustment_df[
    [
        "Fiscal Year",
        "Shares Repurchased",
        "Shares Issued Net",
        "Net Share Effect",
        "Net Share Effect Direction",
        "Buyback Offset Ratio",
        "Buyback Offset Ratio Display",
        "Buyback Offset Classification",
        "Cash Spent on Buybacks",
        "Cash Spent Display",
        "Shares Outstanding Growth",
        "Shares Outstanding Growth Percentage",
    ]
]

print(buyback_adjustment_df.to_string(index=False, na_rep="N/A"))

expected_net_share_effect = [-483.361, -393.364, -433.275, -343.526]
expected_offset_ratios = [6.67, 6.04, 7.56, 6.91]
expected_cash_spent = [89402, 77550, 94949, 90711]
expected_classification = "Buybacks more than offset share issuance"
net_effect_tolerance = 1e-9
ratio_tolerance = 0.005

validation_passed = (
    len(buyback_adjustment_df) == 4
    and buyback_adjustment_df["Fiscal Year"].tolist() == required_years
    and all(
        abs(actual - expected) <= net_effect_tolerance
        for actual, expected in zip(
            buyback_adjustment_df["Net Share Effect"],
            expected_net_share_effect,
        )
    )
    and all(
        abs(actual - expected) <= ratio_tolerance
        for actual, expected in zip(
            buyback_adjustment_df["Buyback Offset Ratio"],
            expected_offset_ratios,
        )
    )
    and buyback_adjustment_df["Cash Spent on Buybacks"].tolist()
    == expected_cash_spent
    and buyback_adjustment_df["Net Share Effect Direction"].eq(
        "Net share reduction"
    ).all()
    and buyback_adjustment_df["Buyback Offset Classification"].eq(
        expected_classification
    ).all()
)

if validation_passed:
    print("Buyback adjustment validated successfully")
else:
    print("Buyback adjustment validation failed")
