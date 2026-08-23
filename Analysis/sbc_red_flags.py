import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Reuse the existing SBC, fiscal-year-end share, and buyback outputs.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.buyback_adjustment import buyback_adjustment_df
    from Analysis.sbc_vs_dilution import significant_dilution_threshold
    from Calculations.sbc_analysis import sbc_analysis_df
    from Calculations.share_dilution import share_dilution_df


REQUIRED_YEARS = [2022, 2023, 2024, 2025]
LARGE_SBC_THRESHOLD = 0.10
LARGE_SBC_RULE = "SBC / abs(Net Income) >= 10%"
DILUTION_RULE = "Shares Outstanding Growth >= 1%"
BUYBACK_OFFSET_RULE = (
    "Shares Issued Net > 0 AND Shares Repurchased >= Shares Issued Net; "
    "Shares Issued Net > 0 AND Shares Repurchased < Shares Issued Net"
)
SEVERITY_PRIORITY = {"None": 0, "Low": 1, "Medium": 2}


sbc_by_year = sbc_analysis_df.set_index("Fiscal Year")
shares_by_year = share_dilution_df.set_index("Fiscal Year")
buybacks_by_year = buyback_adjustment_df.set_index("Fiscal Year")
analysis_rows = []

for fiscal_year in REQUIRED_YEARS:
    sbc = sbc_by_year.loc[fiscal_year]
    shares = shares_by_year.loc[fiscal_year]
    buybacks = buybacks_by_year.loc[fiscal_year]

    sbc_to_net_income = sbc["SBC"] / abs(sbc["Net Income"])
    large_sbc_flag = bool(sbc_to_net_income >= LARGE_SBC_THRESHOLD)
    large_sbc_result = "Review" if large_sbc_flag else "No Flag"
    large_sbc_severity = "Medium" if large_sbc_flag else "None"

    shares_growth = shares["Shares Outstanding Growth"]
    dilution_flag = bool(
        not pd.isna(shares_growth)
        and shares_growth >= significant_dilution_threshold
    )
    dilution_result = "Flag" if dilution_flag else "No Flag"
    dilution_severity = "Medium" if dilution_flag else "None"

    shares_issued = buybacks["Shares Issued Net"]
    shares_repurchased = buybacks["Shares Repurchased"]
    if shares_issued > 0 and shares_repurchased >= shares_issued:
        buyback_offset_flag = True
        buyback_classification = "Buybacks more than offset share issuance"
    elif shares_issued > 0 and shares_repurchased < shares_issued:
        buyback_offset_flag = True
        buyback_classification = "Buybacks partially offset share issuance"
    else:
        buyback_offset_flag = False
        buyback_classification = "No positive net share issuance to offset"
    buyback_offset_result = "Review" if buyback_offset_flag else "No Flag"
    buyback_offset_severity = "Low" if buyback_offset_flag else "None"

    severities = [
        large_sbc_severity,
        dilution_severity,
        buyback_offset_severity,
    ]
    overall_severity = max(severities, key=SEVERITY_PRIORITY.get)
    signal_by_severity = {
        "Medium": "SBC requires investigation",
        "Low": "SBC and buyback interaction requires review",
        "None": "No SBC warning",
    }

    explanations = []
    if large_sbc_flag:
        explanations.append(
            "Stock-based compensation is at least 10% of reported net income "
            "under the current analyst threshold; its economic significance "
            "should be reviewed."
        )
    if dilution_flag:
        explanations.append(
            "Fiscal-year-end shares outstanding increased by at least the "
            "existing 1% significant-dilution threshold."
        )
    if buyback_offset_flag:
        explanations.append(
            "Share repurchases offset positive net share issuance during the "
            "year; the cash cost of the repurchases remains economically relevant."
        )
    if not explanations:
        explanations.append("Existing SBC and dilution rules did not trigger.")

    analysis_rows.append(
        {
            "Fiscal Year": fiscal_year,
            "SBC": sbc["SBC"],
            "Net Income": sbc["Net Income"],
            "SBC / Net Income": sbc_to_net_income,
            "SBC / Net Income Display": f"{sbc_to_net_income:.2%}",
            "Large SBC Rule": LARGE_SBC_RULE,
            "Large SBC Flag": large_sbc_flag,
            "Large SBC Result": large_sbc_result,
            "Large SBC Severity": large_sbc_severity,
            "Shares Outstanding": shares["Shares Outstanding"],
            "Shares Outstanding Growth": shares_growth,
            "Shares Outstanding Growth Display": (
                "N/A" if pd.isna(shares_growth) else f"{shares_growth:.2%}"
            ),
            "Dilution Rule": DILUTION_RULE,
            "Dilution Flag": dilution_flag,
            "Dilution Result": dilution_result,
            "Dilution Severity": dilution_severity,
            "Shares Issued Net": shares_issued,
            "Shares Repurchased": shares_repurchased,
            "Buyback Offset Ratio": buybacks["Buyback Offset Ratio"],
            "Buyback Offset Ratio Display": buybacks[
                "Buyback Offset Ratio Display"
            ],
            "Net Share Effect": buybacks["Net Share Effect"],
            "Cash Spent on Buybacks": buybacks["Cash Spent on Buybacks"],
            "Cash Spent Display": buybacks["Cash Spent Display"],
            "Buyback Offset Classification": buyback_classification,
            "Buyback Offset Flag": buyback_offset_flag,
            "Buyback Offset Result": buyback_offset_result,
            "Buyback Offset Severity": buyback_offset_severity,
            "SBC Signal": signal_by_severity[overall_severity],
            "Overall SBC Severity": overall_severity,
            "Explanation": " ".join(explanations),
        }
    )


sbc_red_flags_df = pd.DataFrame(analysis_rows)
sbc_attention_df = sbc_red_flags_df.loc[
    sbc_red_flags_df["Overall SBC Severity"] != "None"
].copy()


validation_errors = []
if len(sbc_red_flags_df) != 4:
    validation_errors.append("The analysis must contain exactly four rows")
if sbc_red_flags_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("Fiscal years must be 2022 through 2025")

source_sbc_ratios = sbc_analysis_df.set_index("Fiscal Year")["SBC / Net Income"]
output_sbc_ratios = sbc_red_flags_df.set_index("Fiscal Year")["SBC / Net Income"]
if not output_sbc_ratios.equals(source_sbc_ratios):
    validation_errors.append("SBC / Net Income does not match Task 21")
if LARGE_SBC_THRESHOLD != 0.10:
    validation_errors.append("The large-SBC threshold must remain 10%")

by_year = sbc_red_flags_df.set_index("Fiscal Year")
expected_large_sbc_flags = {
    2022: False,
    2023: True,
    2024: True,
    2025: True,
}
if by_year["Large SBC Flag"].to_dict() != expected_large_sbc_flags:
    validation_errors.append("Apple large-SBC flags are unexpected")
if significant_dilution_threshold != 0.01:
    validation_errors.append("The significant-dilution threshold must remain 1%")
if by_year.loc[2023:2025, "Dilution Flag"].any():
    validation_errors.append("2023-2025 must not trigger significant dilution")

buyback_columns = [
    "Shares Issued Net",
    "Shares Repurchased",
    "Buyback Offset Ratio",
    "Net Share Effect",
    "Cash Spent on Buybacks",
]
source_buybacks = buyback_adjustment_df.set_index("Fiscal Year")[buyback_columns]
output_buybacks = sbc_red_flags_df.set_index("Fiscal Year")[buyback_columns]
try:
    pd.testing.assert_frame_equal(output_buybacks, source_buybacks)
except AssertionError:
    validation_errors.append("Buyback figures do not match Task 24")
if by_year["Cash Spent on Buybacks"].tolist() != [
    89402,
    77550,
    94949,
    90711,
]:
    validation_errors.append("Apple cash spent on buybacks is unexpected")

severity_columns = [
    "Large SBC Severity",
    "Dilution Severity",
    "Buyback Offset Severity",
    "Overall SBC Severity",
]
if sbc_red_flags_df[severity_columns].eq("High").any().any():
    validation_errors.append("Task 33 must not create High severity")
if sbc_attention_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("All four Apple years must appear in the review table")

print("SBC red-flag analysis:")
print(sbc_red_flags_df.to_string(index=False, na_rep="N/A"))
print("\nYears requiring attention:")
print(sbc_attention_df.to_string(index=False, na_rep="N/A"))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("SBC red flags validated successfully")
