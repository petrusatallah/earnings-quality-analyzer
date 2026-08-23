import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress source-module output so this analysis prints only its two requested
# tables and validation result.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.manual_one_off_classification import (
        manual_one_off_classification_df,
    )
    from Data.one_off_items import one_off_items_df, required_categories


def build_category_summary(items, categories):
    available = items.loc[items["Availability"] == "Available"]
    identified_years = available.groupby("Category")["Fiscal Year"].agg(
        lambda years: sorted(years.unique())
    )

    summary_rows = []
    for category in categories:
        fiscal_years = identified_years.get(category, [])
        years_appearing = len(fiscal_years)
        repeated = years_appearing >= 2
        summary_rows.append(
            {
                "Category": category,
                "Years Appearing": years_appearing,
                "Fiscal Years Identified": (
                    ", ".join(str(year) for year in fiscal_years)
                    if fiscal_years
                    else "None"
                ),
                "Repeated One-Off": repeated,
                "Review Status": (
                    "Review recurring nature"
                    if repeated
                    else "No repeated pattern detected"
                ),
            }
        )

    return pd.DataFrame(summary_rows)


original_manual_classification_df = manual_one_off_classification_df.copy(deep=True)
category_summary_df = build_category_summary(one_off_items_df, required_categories)

available_item_detail_df = manual_one_off_classification_df.loc[
    manual_one_off_classification_df["Availability"] == "Available"
].merge(
    category_summary_df[["Category", "Repeated One-Off", "Review Status"]],
    on="Category",
    how="left",
    validate="many_to_one",
)


validation_errors = []

if len(category_summary_df) != 7 or set(category_summary_df["Category"]) != set(
    required_categories
):
    validation_errors.append("All seven approved categories must appear in the summary")

available_source_rows = one_off_items_df.loc[
    one_off_items_df["Availability"] == "Available"
]
expected_counts = (
    available_source_rows.groupby("Category")["Fiscal Year"].nunique().to_dict()
)
actual_counts = category_summary_df.set_index("Category")["Years Appearing"].to_dict()
if any(
    actual_counts[category] != expected_counts.get(category, 0)
    for category in required_categories
):
    validation_errors.append(
        "Years Appearing must count distinct years from available rows only"
    )

unusual_tax_summary = category_summary_df.loc[
    category_summary_df["Category"] == "Unusual tax gains/losses"
]
if len(unusual_tax_summary) != 1 or not (
    unusual_tax_summary.iloc[0]["Years Appearing"] == 1
    and unusual_tax_summary.iloc[0]["Fiscal Years Identified"] == "2024"
):
    validation_errors.append(
        "The 2024 unusual tax item must produce Years Appearing = 1"
    )

if category_summary_df["Repeated One-Off"].any():
    validation_errors.append("No Apple category should currently be repeated")

try:
    pd.testing.assert_frame_equal(
        manual_one_off_classification_df, original_manual_classification_df
    )
except AssertionError:
    validation_errors.append("Manual Classification data was modified")

# Temporary rule test only; this does not alter the Apple benchmark.
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
repetition_test_summary = build_category_summary(
    repetition_test_data, ["Restructuring"]
).iloc[0]
if not (
    repetition_test_summary["Years Appearing"] == 2
    and repetition_test_summary["Repeated One-Off"]
    and repetition_test_summary["Review Status"] == "Review recurring nature"
):
    validation_errors.append("The internal repetition detection test failed")

detail_fields = [
    "Fiscal Year",
    "Category",
    "Description",
    "Value",
    "Direction",
    "Manual Classification",
    "Repeated One-Off",
    "Review Status",
]

print("Category summary:")
print(category_summary_df.to_string(index=False))
print("\nAvailable item detail:")
print(available_item_detail_df[detail_fields].to_string(index=False))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Repeated one-off detection validated successfully")
