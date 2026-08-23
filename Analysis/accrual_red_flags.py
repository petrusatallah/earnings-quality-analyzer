import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Reuse the established year-over-year calculation outputs.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.accrual_cash_comparison import comparison_df


EXPECTED_YEARS = [2023, 2024, 2025]
AR_GAP_THRESHOLD = 0.10
AR_RULE = "AR Growth - Revenue Growth >= 10 percentage points"
NI_OCF_RULE = "Net Income Growth > 0 AND OCF Growth < 0"


def classify_accrual_signal(ar_flag, ni_ocf_flag):
    if ar_flag and ni_ocf_flag:
        return (
            True,
            "Strong accrual warning",
            "High",
            "Accounts receivable grew materially faster than revenue while net "
            "income increased and operating cash flow declined; multiple "
            "accrual-quality signals require investigation.",
        )
    if ar_flag:
        return (
            False,
            "Accrual warning",
            "Medium",
            "Accounts receivable grew materially faster than revenue under the "
            "existing threshold; collection quality or revenue recognition timing "
            "may require investigation.",
        )
    if ni_ocf_flag:
        return (
            False,
            "Accrual warning",
            "Medium",
            "Net income increased while operating cash flow declined; the "
            "earnings-to-cash relationship requires investigation.",
        )
    return (
        False,
        "No accrual warning",
        "None",
        "Existing accrual rules did not trigger.",
    )


analysis_rows = []
for _, source_row in comparison_df.iterrows():
    fiscal_year = int(source_row["Fiscal Year"])
    ar_growth = source_row["AR Growth"]
    revenue_growth = source_row["Revenue Growth"]
    ar_revenue_gap = ar_growth - revenue_growth
    ar_flag = bool(ar_revenue_gap >= AR_GAP_THRESHOLD)

    net_income_growth = source_row["Net Income Growth"]
    ocf_growth = source_row["OCF Growth"]
    ni_ocf_flag = bool(net_income_growth > 0 and ocf_growth < 0)
    combined_flag, signal, severity, explanation = classify_accrual_signal(
        ar_flag, ni_ocf_flag
    )

    analysis_rows.append(
        {
            "Fiscal Year": fiscal_year,
            "AR Growth": ar_growth,
            "Revenue Growth": revenue_growth,
            "AR Revenue Gap": ar_revenue_gap,
            "AR Revenue Gap Display": f"{ar_revenue_gap * 100:.2f}pp",
            "AR Rule": AR_RULE,
            "AR Flag": ar_flag,
            "Net Income Growth": net_income_growth,
            "OCF Growth": ocf_growth,
            "NI OCF Rule": NI_OCF_RULE,
            "NI OCF Flag": ni_ocf_flag,
            "Combined Accrual Flag": combined_flag,
            "Accrual Signal": signal,
            "Severity": severity,
            "Explanation": explanation,
        }
    )


accrual_red_flags_df = pd.DataFrame(analysis_rows)
combined_warning_df = accrual_red_flags_df.loc[
    accrual_red_flags_df["Combined Accrual Flag"]
].copy()

# Backward-compatible per-rule view used by the Task 30 consolidated table.
rule_result_rows = []
for _, row in accrual_red_flags_df.iterrows():
    rule_result_rows.extend(
        [
            {
                "Fiscal Year": row["Fiscal Year"],
                "Rule Name": "AR Growth vs Revenue Growth",
                "Exact Rule": row["AR Rule"],
                "Relevant Values": (
                    f"AR Growth = {row['AR Growth']:.2%}, "
                    f"Revenue Growth = {row['Revenue Growth']:.2%}, "
                    f"Difference = {row['AR Revenue Gap'] * 100:.2f} "
                    "percentage points"
                ),
                "Flag": row["AR Flag"],
            },
            {
                "Fiscal Year": row["Fiscal Year"],
                "Rule Name": "Net Income Up / OCF Down",
                "Exact Rule": row["NI OCF Rule"],
                "Relevant Values": (
                    f"NI Growth = {row['Net Income Growth']:.2%}, "
                    f"OCF Growth = {row['OCF Growth']:.2%}"
                ),
                "Flag": row["NI OCF Flag"],
            },
        ]
    )
accrual_rule_results_df = pd.DataFrame(rule_result_rows)
triggered_flags_df = accrual_rule_results_df.loc[
    accrual_rule_results_df["Flag"]
].copy()


validation_errors = []
if len(accrual_red_flags_df) != 3:
    validation_errors.append("The analysis must contain exactly three rows")
if accrual_red_flags_df["Fiscal Year"].tolist() != EXPECTED_YEARS:
    validation_errors.append("Fiscal years must be 2023, 2024, and 2025")
if AR_GAP_THRESHOLD != 0.10 or AR_RULE != (
    "AR Growth - Revenue Growth >= 10 percentage points"
):
    validation_errors.append("The existing AR threshold was changed")
if NI_OCF_RULE != "Net Income Growth > 0 AND OCF Growth < 0":
    validation_errors.append("The existing NI/OCF rule was changed")

by_year = accrual_red_flags_df.set_index("Fiscal Year")
expected_results = {
    2023: (False, False, False, "No accrual warning", "None"),
    2024: (True, False, False, "Accrual warning", "Medium"),
    2025: (True, True, True, "Strong accrual warning", "High"),
}
for year, expected in expected_results.items():
    row = by_year.loc[year]
    actual = (
        row["AR Flag"],
        row["NI OCF Flag"],
        row["Combined Accrual Flag"],
        row["Accrual Signal"],
        row["Severity"],
    )
    if actual != expected:
        validation_errors.append(f"Unexpected accrual result for {year}")

if combined_warning_df["Fiscal Year"].tolist() != [2025]:
    validation_errors.append("Only 2025 may appear in the combined-warning table")

display_df = accrual_red_flags_df.copy()
for column in [
    "AR Growth",
    "Revenue Growth",
    "Net Income Growth",
    "OCF Growth",
]:
    display_df[column] = display_df[column].map(lambda value: f"{value:.2%}")

print("Accrual red-flag analysis:")
print(display_df.to_string(index=False))
print("\nCombined accrual warnings:")
print(
    display_df.loc[display_df["Combined Accrual Flag"]].to_string(index=False)
)

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Accrual red flags validated successfully")
