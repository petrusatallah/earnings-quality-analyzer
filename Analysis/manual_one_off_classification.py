import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# The source module prints its own Task 25 output when imported. Suppress it so
# this module prints only the manual-classification analysis.
with contextlib.redirect_stdout(io.StringIO()):
    from Data.one_off_items import one_off_items_df


# Analyst-editable manual decisions. Keep these separate from the application
# logic so classifications can be reviewed and updated without changing rules.
manual_classifications = {
    (2024, "Unusual tax gains/losses"): "Non-recurring",
}

allowed_available_classifications = {"Recurring", "Non-recurring", "Uncertain"}
allowed_classifications = allowed_available_classifications | {"Not Applicable"}

# Preserve the imported source and perform classification on a separate copy.
original_one_off_items_df = one_off_items_df.copy(deep=True)
manual_one_off_classification_df = one_off_items_df.copy(deep=True)


def apply_manual_classification(row):
    if row["Availability"] == "Not Available":
        return pd.Series(["Not Applicable", "Not Applicable"])

    key = (row["Fiscal Year"], row["Category"])
    if key in manual_classifications:
        return pd.Series([manual_classifications[key], "Reviewed"])

    return pd.Series(["Uncertain", "Needs manual review"])


manual_one_off_classification_df[
    ["Manual Classification", "Manual Review Status"]
] = manual_one_off_classification_df.apply(apply_manual_classification, axis=1)


validation_errors = []

try:
    pd.testing.assert_frame_equal(one_off_items_df, original_one_off_items_df)
except AssertionError:
    validation_errors.append("The original one-off dataset was modified")

invalid_mapping_values = set(manual_classifications.values()) - (
    allowed_available_classifications
)
if invalid_mapping_values:
    validation_errors.append(
        f"Invalid manual mapping values: {sorted(invalid_mapping_values)}"
    )

available_rows = manual_one_off_classification_df["Availability"].eq("Available")
unavailable_rows = manual_one_off_classification_df["Availability"].eq(
    "Not Available"
)

if not manual_one_off_classification_df.loc[
    available_rows, "Manual Classification"
].isin(allowed_available_classifications).all():
    validation_errors.append(
        "Every available item must have a valid Manual Classification"
    )

if not manual_one_off_classification_df.loc[
    unavailable_rows, "Manual Classification"
].eq("Not Applicable").all():
    validation_errors.append("Unavailable items must be Not Applicable")

mapped_keys = set(manual_classifications)
row_keys = list(
    zip(
        manual_one_off_classification_df["Fiscal Year"],
        manual_one_off_classification_df["Category"],
    )
)
mapped_rows = pd.Series(
    [key in mapped_keys for key in row_keys],
    index=manual_one_off_classification_df.index,
)
unmapped_available_rows = available_rows & ~mapped_rows

if not (
    manual_one_off_classification_df.loc[
        unmapped_available_rows, "Manual Classification"
    ].eq("Uncertain").all()
    and manual_one_off_classification_df.loc[
        unmapped_available_rows, "Manual Review Status"
    ].eq("Needs manual review").all()
):
    validation_errors.append(
        "Available items without mappings must default to Uncertain and need review"
    )

known_item = manual_one_off_classification_df.loc[
    (manual_one_off_classification_df["Fiscal Year"] == 2024)
    & (
        manual_one_off_classification_df["Category"]
        == "Unusual tax gains/losses"
    )
]
if len(known_item) != 1:
    validation_errors.append("The 2024 unusual tax item must exist exactly once")
else:
    known_item = known_item.iloc[0]
    if known_item["Manual Classification"] != "Non-recurring":
        validation_errors.append(
            "The 2024 unusual tax item must be classified as Non-recurring"
        )
    if known_item["Manual Review Status"] != "Reviewed":
        validation_errors.append(
            "The 2024 unusual tax item Manual Review Status must be Reviewed"
        )

invalid_classifications = set(
    manual_one_off_classification_df["Manual Classification"]
) - allowed_classifications
if invalid_classifications:
    validation_errors.append(
        f"Invalid Manual Classification values: {sorted(invalid_classifications)}"
    )

output_fields = [
    "Fiscal Year",
    "Category",
    "Description",
    "Value",
    "Direction",
    "Tax Basis",
    "Manual Classification",
    "Manual Review Status",
]
identified_items = manual_one_off_classification_df.loc[available_rows, output_fields]
print(identified_items.to_string(index=False))

classification_order = ["Recurring", "Non-recurring", "Uncertain"]
classification_summary = (
    identified_items["Manual Classification"]
    .value_counts()
    .reindex(classification_order, fill_value=0)
)
print("\nClassification summary:")
print(classification_summary.to_string())

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Manual one-off classification validated successfully")
