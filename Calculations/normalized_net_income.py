import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress the source modules' own output so this calculation prints only its
# adjustment audit trail and normalized Net Income table.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.manual_one_off_classification import (
        manual_one_off_classification_df,
    )
    from Data.apple_test_dataset import apple_financial_data_df


required_years = [2022, 2023, 2024, 2025]


def calculate_item_adjustment(item):
    classification = item["Manual Classification"]

    if classification == "Recurring":
        return pd.Series([0.0, "No adjustment - recurring"])
    if classification == "Uncertain":
        return pd.Series([0.0, "No adjustment - uncertain"])
    if classification != "Non-recurring":
        return pd.Series([0.0, "Not Applicable"])

    # No tax rate is estimated. A disclosed tax item or after-tax amount can be
    # used directly; a pre-tax amount remains excluded until an after-tax
    # adjustment is available.
    if item["Tax Basis"] == "Pre-tax":
        return pd.Series([0.0, "Tax treatment required"])
    if item["Tax Basis"] not in {"After-tax", "Tax item"}:
        return pd.Series([0.0, "Tax treatment required"])

    if item["Direction"] == "Gain":
        return pd.Series([-item["Value"], "Adjusted"])
    if item["Direction"] == "Charge":
        return pd.Series([item["Value"], "Adjusted"])
    return pd.Series([0.0, "Direction required"])


available_items = manual_one_off_classification_df.loc[
    manual_one_off_classification_df["Availability"] == "Available"
].copy()
available_items[["Normalization Adjustment", "Adjustment Status"]] = (
    available_items.apply(calculate_item_adjustment, axis=1)
)

available_items["Non-recurring Gains Removed"] = available_items[
    "Normalization Adjustment"
].where(available_items["Normalization Adjustment"] < 0, 0).abs()
available_items["Non-recurring Charges Added Back"] = available_items[
    "Normalization Adjustment"
].where(available_items["Normalization Adjustment"] > 0, 0)

adjustments_by_year = available_items.groupby("Fiscal Year", as_index=False).agg(
    {
        "Non-recurring Gains Removed": "sum",
        "Non-recurring Charges Added Back": "sum",
        "Normalization Adjustment": "sum",
    }
)
adjustments_by_year = adjustments_by_year.rename(
    columns={"Normalization Adjustment": "Net Normalization Adjustment"}
)

reported_net_income = apple_financial_data_df.loc[
    apple_financial_data_df["Metric"] == "Net Income",
    ["Fiscal Year", "Value"],
].rename(columns={"Value": "Reported Net Income"})

normalized_net_income_df = reported_net_income.merge(
    adjustments_by_year, on="Fiscal Year", how="left"
).sort_values("Fiscal Year")

adjustment_columns = [
    "Non-recurring Gains Removed",
    "Non-recurring Charges Added Back",
    "Net Normalization Adjustment",
]
normalized_net_income_df[adjustment_columns] = normalized_net_income_df[
    adjustment_columns
].fillna(0.0)
normalized_net_income_df["Normalized Net Income"] = (
    normalized_net_income_df["Reported Net Income"]
    + normalized_net_income_df["Net Normalization Adjustment"]
)
normalized_net_income_df["Normalized NI Difference"] = (
    normalized_net_income_df["Normalized Net Income"]
    - normalized_net_income_df["Reported Net Income"]
)
reported_ni_denominator = normalized_net_income_df["Reported Net Income"].abs()
normalized_net_income_df["Normalized NI Difference Percentage"] = (
    normalized_net_income_df["Normalized NI Difference"]
    / reported_ni_denominator.where(reported_ni_denominator != 0)
)


validation_errors = []

if len(normalized_net_income_df) != 4:
    validation_errors.append("Expected exactly four normalized Net Income rows")
if normalized_net_income_df["Fiscal Year"].tolist() != required_years:
    validation_errors.append("Normalized Net Income years must be 2022 through 2025")

verified_reported_ni = {2022: 99803, 2023: 96995, 2024: 93736, 2025: 112010}
actual_reported_ni = normalized_net_income_df.set_index("Fiscal Year")[
    "Reported Net Income"
].to_dict()
if actual_reported_ni != verified_reported_ni:
    validation_errors.append("Reported Net Income does not match the Apple dataset")

nonrecurring_items = available_items["Manual Classification"].eq("Non-recurring")
eligible_tax_basis = available_items["Tax Basis"].isin({"After-tax", "Tax item"})
expected_adjusted_items = nonrecurring_items & eligible_tax_basis & available_items[
    "Direction"
].isin({"Gain", "Charge"})
if not available_items.loc[
    ~expected_adjusted_items, "Normalization Adjustment"
].eq(0).all():
    validation_errors.append("Only eligible manually non-recurring items may affect NI")

if not available_items.loc[
    available_items["Manual Classification"].isin({"Recurring", "Uncertain"}),
    "Normalization Adjustment",
].eq(0).all():
    validation_errors.append("Recurring and uncertain items must not affect NI")

# Exercise the direction and classification rules independently of the current
# benchmark mix, which presently contains only one available charge.
rule_test_base = {
    "Value": 100.0,
    "Tax Basis": "After-tax",
    "Direction": "Gain",
    "Manual Classification": "Non-recurring",
}
if calculate_item_adjustment(pd.Series(rule_test_base)).iloc[0] != -100.0:
    validation_errors.append("Non-recurring gains must be subtracted")
rule_test_base["Direction"] = "Charge"
if calculate_item_adjustment(pd.Series(rule_test_base)).iloc[0] != 100.0:
    validation_errors.append("Non-recurring charges must be added back")
rule_test_base["Tax Basis"] = "Pre-tax"
if calculate_item_adjustment(pd.Series(rule_test_base)).iloc[0] != 0.0:
    validation_errors.append("Pre-tax items must remain excluded without tax treatment")

known_item = available_items.loc[
    (available_items["Fiscal Year"] == 2024)
    & (available_items["Category"] == "Unusual tax gains/losses")
]
if len(known_item) != 1:
    validation_errors.append("The 2024 unusual tax item must exist exactly once")
else:
    known_item = known_item.iloc[0]
    if not (
        known_item["Tax Basis"] == "Tax item"
        and known_item["Normalization Adjustment"] == known_item["Value"] == 10200
        and known_item["Adjustment Status"] == "Adjusted"
    ):
        validation_errors.append(
            "The 2024 tax charge must be added back directly without another tax calculation"
        )

expected_normalized_ni = {2022: 99803, 2023: 96995, 2024: 103936, 2025: 112010}
normalized_by_year = normalized_net_income_df.set_index("Fiscal Year")
for fiscal_year, expected_value in expected_normalized_ni.items():
    if normalized_by_year.loc[fiscal_year, "Normalized Net Income"] != expected_value:
        validation_errors.append(
            f"Normalized Net Income for {fiscal_year} must be {expected_value:,}"
        )
if normalized_by_year.loc[2024, "Net Normalization Adjustment"] != 10200:
    validation_errors.append("The 2024 Net Normalization Adjustment must be 10,200")

detail_fields = [
    "Fiscal Year",
    "Category",
    "Description",
    "Value",
    "Direction",
    "Tax Basis",
    "Manual Classification",
    "Normalization Adjustment",
    "Adjustment Status",
]
print(available_items[detail_fields].to_string(index=False))
print("\nNormalized Net Income:")
print(normalized_net_income_df.to_string(index=False))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Normalized Net Income validated successfully")
