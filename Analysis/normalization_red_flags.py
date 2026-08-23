import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Reuse the established earnings comparison and repeated-item analysis.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.manual_one_off_classification import (
        manual_one_off_classification_df,
    )
    from Analysis.repeated_one_off_detection import (
        build_category_summary,
        category_summary_df,
    )
    from Analysis.reported_vs_normalized_earnings import (
        reported_vs_normalized_earnings_df,
    )


REQUIRED_YEARS = [2022, 2023, 2024, 2025]
LARGE_DIFFERENCE_THRESHOLD = 0.10
LARGE_DIFFERENCE_RULE = "abs(Percentage Difference) >= 10%"
REPEATED_ONE_OFF_RULE = "Years Appearing >= 2"


def classify_normalization(repeated_flag, large_difference_flag):
    if repeated_flag and large_difference_flag:
        return (
            "Strong normalization warning",
            "High",
            "A repeated unusual-item category is present and normalization "
            "changes reported earnings by at least 10%; the treatment of unusual "
            "items requires heightened review.",
        )
    if large_difference_flag:
        return (
            "Normalization requires investigation",
            "Medium",
            "Normalized net income differs from reported net income by at least "
            "10% under the current analyst threshold; the normalization adjustment "
            "requires investigation.",
        )
    if repeated_flag:
        return (
            "Normalization requires investigation",
            "Medium",
            "The same unusual-item category appears across multiple fiscal years; "
            "its recurring nature should be reviewed before automatically excluding "
            "it from earnings.",
        )
    return (
        "No normalization warning",
        "None",
        "Existing normalization red-flag rules did not trigger.",
    )


original_manual_classification_df = manual_one_off_classification_df.copy(deep=True)
comparison_by_year = reported_vs_normalized_earnings_df.set_index("Fiscal Year")
available_items = manual_one_off_classification_df.loc[
    manual_one_off_classification_df["Availability"] == "Available"
]
repeated_summaries = category_summary_df.loc[
    category_summary_df["Repeated One-Off"]
]

analysis_rows = []
for fiscal_year in REQUIRED_YEARS:
    comparison = comparison_by_year.loc[fiscal_year]
    percentage_difference = comparison["Percentage Difference"]
    large_difference_flag = bool(
        not pd.isna(percentage_difference)
        and abs(percentage_difference) >= LARGE_DIFFERENCE_THRESHOLD
    )

    identified_categories = sorted(
        available_items.loc[
            available_items["Fiscal Year"] == fiscal_year, "Category"
        ].unique()
    )
    repeated_categories = sorted(
        summary["Category"]
        for _, summary in repeated_summaries.iterrows()
        if str(fiscal_year) in summary["Fiscal Years Identified"].split(", ")
    )
    repeated_flag = bool(repeated_categories)
    signal, overall_severity, explanation = classify_normalization(
        repeated_flag, large_difference_flag
    )

    analysis_rows.append(
        {
            "Fiscal Year": fiscal_year,
            "Reported Net Income": comparison["Reported Net Income"],
            "Normalized Net Income": comparison["Normalized Net Income"],
            "Difference": comparison["Difference"],
            "Percentage Difference": percentage_difference,
            "Percentage Difference Display": comparison[
                "Percentage Difference Display"
            ],
            "Earnings Adjustment Direction": comparison[
                "Earnings Adjustment Direction"
            ],
            "Large Difference Rule": LARGE_DIFFERENCE_RULE,
            "Large Normalization Difference Flag": large_difference_flag,
            "Large Normalization Difference Result": (
                "Flag" if large_difference_flag else "No Flag"
            ),
            "Large Normalization Difference Severity": (
                "Medium" if large_difference_flag else "None"
            ),
            "One-Off Categories Identified": (
                ", ".join(identified_categories)
                if identified_categories
                else "None"
            ),
            "Repeated Categories": (
                ", ".join(repeated_categories) if repeated_categories else "None"
            ),
            "Repeated One-Off Rule": REPEATED_ONE_OFF_RULE,
            "Repeated One-Off Flag": repeated_flag,
            "Repeated One-Off Result": "Review" if repeated_flag else "No Flag",
            "Repeated One-Off Severity": "Medium" if repeated_flag else "None",
            "Normalization Signal": signal,
            "Overall Severity": overall_severity,
            "Explanation": explanation,
        }
    )


normalization_red_flags_df = pd.DataFrame(analysis_rows)
normalization_attention_df = normalization_red_flags_df.loc[
    normalization_red_flags_df["Overall Severity"] != "None"
].copy()


validation_errors = []
if len(normalization_red_flags_df) != 4:
    validation_errors.append("The analysis must contain exactly four rows")
if normalization_red_flags_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("Fiscal years must be 2022 through 2025")

comparison_columns = [
    "Reported Net Income",
    "Normalized Net Income",
    "Difference",
    "Percentage Difference",
    "Percentage Difference Display",
    "Earnings Adjustment Direction",
]
source_comparison = reported_vs_normalized_earnings_df.set_index("Fiscal Year")[
    comparison_columns
]
output_comparison = normalization_red_flags_df.set_index("Fiscal Year")[
    comparison_columns
]
try:
    pd.testing.assert_frame_equal(output_comparison, source_comparison)
except AssertionError:
    validation_errors.append("Task 28 earnings comparison values were changed")

if LARGE_DIFFERENCE_THRESHOLD != 0.10:
    validation_errors.append("The large-difference threshold must remain 10%")
if not abs(-0.10) >= LARGE_DIFFERENCE_THRESHOLD:
    validation_errors.append("The large-difference test must use absolute value")
expected_large_flags = {2022: False, 2023: False, 2024: True, 2025: False}
by_year = normalization_red_flags_df.set_index("Fiscal Year")
if by_year["Large Normalization Difference Flag"].to_dict() != expected_large_flags:
    validation_errors.append("Apple large-difference flags are unexpected")
expected_2024_percentage = 10200 / abs(93736)
if abs(by_year.loc[2024, "Percentage Difference"] - expected_2024_percentage) > 1e-12:
    validation_errors.append("The 2024 percentage difference must be about 10.88%")
if by_year.loc[2024, "Overall Severity"] != "Medium":
    validation_errors.append("The 2024 overall severity must be Medium")
if by_year["Repeated One-Off Flag"].any():
    validation_errors.append("Apple must not trigger a repeated one-off review")
if not category_summary_df["Repeated One-Off"].eq(
    category_summary_df["Years Appearing"] >= 2
).all():
    validation_errors.append("Task 29 repeated-item logic was not preserved")

# Temporary rule tests only; the Apple data and manual classifications are not
# modified.
repetition_test_data = pd.DataFrame(
    [
        {
            "Fiscal Year": 2023,
            "Category": "Restructuring",
            "Availability": "Available",
        },
        {
            "Fiscal Year": 2024,
            "Category": "Restructuring",
            "Availability": "Available",
        },
    ]
)
repetition_test = build_category_summary(
    repetition_test_data, ["Restructuring"]
).iloc[0]
if not (
    repetition_test["Years Appearing"] == 2
    and repetition_test["Repeated One-Off"]
    and repetition_test["Review Status"] == "Review recurring nature"
):
    validation_errors.append("The temporary repetition test did not trigger")

test_signal, test_severity, _ = classify_normalization(True, True)
if not (
    test_signal == "Strong normalization warning" and test_severity == "High"
):
    validation_errors.append("The temporary combined test did not produce High")

try:
    pd.testing.assert_frame_equal(
        manual_one_off_classification_df, original_manual_classification_df
    )
except AssertionError:
    validation_errors.append("Manual classifications were modified")
if normalization_attention_df["Fiscal Year"].tolist() != [2024]:
    validation_errors.append("Only 2024 may appear in the attention table")

print("Normalization red-flag analysis:")
print(normalization_red_flags_df.to_string(index=False, na_rep="N/A"))
print("\nYears requiring attention:")
print(normalization_attention_df.to_string(index=False, na_rep="N/A"))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Normalization red flags validated successfully")
