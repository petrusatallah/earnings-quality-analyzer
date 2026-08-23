import pandas as pd


required_fields = [
    "Company",
    "Ticker",
    "Fiscal Year",
    "Category",
    "Description",
    "Value",
    "Units",
    "Direction",
    "Tax Basis",
    "Availability",
    "Source",
    "Source Date",
    "Source Detail",
]

required_years = [2022, 2023, 2024, 2025]
required_categories = [
    "Asset-sale gains",
    "Restructuring",
    "Legal settlements",
    "Impairments",
    "Acquisition-related charges",
    "Unusual tax gains/losses",
    "Other unusual items",
]
approved_directions = {"Gain", "Charge", "Not Available"}
approved_tax_bases = {"Pre-tax", "After-tax", "Tax item", "Not Available"}
approved_availability = {"Available", "Not Available"}

one_off_items = []

for fiscal_year in required_years:
    for category in required_categories:
        record = {
            "Company": "Apple Inc.",
            "Ticker": "AAPL",
            "Fiscal Year": fiscal_year,
            "Category": category,
            "Description": "Not identified in current benchmark",
            "Value": float("nan"),
            "Units": "USD millions",
            "Direction": "Not Available",
            "Tax Basis": "Not Available",
            "Availability": "Not Available",
            "Source": "Not Available",
            "Source Date": "Not Available",
            "Source Detail": "Not Available",
        }

        if fiscal_year == 2024 and category == "Unusual tax gains/losses":
            record.update(
                {
                    "Description": (
                        "One-time income tax charge related to the European "
                        "Commission State Aid Decision"
                    ),
                    "Value": 10200,
                    "Direction": "Charge",
                    "Tax Basis": "Tax item",
                    "Availability": "Available",
                    "Source": "Apple Form 10-K",
                    "Source Date": "2024-11-01",
                    "Source Detail": "Note 7 - Income Taxes",
                }
            )

        one_off_items.append(record)

one_off_items_df = pd.DataFrame(one_off_items, columns=required_fields)


validation_errors = []

if len(one_off_items_df) != 28:
    validation_errors.append(
        f"Expected exactly 28 rows, found {len(one_off_items_df)}"
    )

if set(one_off_items_df["Fiscal Year"]) != set(required_years):
    validation_errors.append("Fiscal years must be exactly 2022, 2023, 2024, 2025")

for fiscal_year in required_years:
    year_categories = one_off_items_df.loc[
        one_off_items_df["Fiscal Year"] == fiscal_year, "Category"
    ]
    if len(year_categories) != len(required_categories) or set(year_categories) != set(
        required_categories
    ):
        validation_errors.append(
            f"Required categories are incomplete or duplicated for {fiscal_year}"
        )

invalid_categories = set(one_off_items_df["Category"]) - set(required_categories)
if invalid_categories:
    validation_errors.append(f"Invalid Category values: {sorted(invalid_categories)}")

invalid_directions = set(one_off_items_df["Direction"]) - approved_directions
if invalid_directions:
    validation_errors.append(f"Invalid Direction values: {sorted(invalid_directions)}")

invalid_tax_bases = set(one_off_items_df["Tax Basis"]) - approved_tax_bases
if invalid_tax_bases:
    validation_errors.append(f"Invalid Tax Basis values: {sorted(invalid_tax_bases)}")

invalid_availability = set(one_off_items_df["Availability"]) - approved_availability
if invalid_availability:
    validation_errors.append(
        f"Invalid Availability values: {sorted(invalid_availability)}"
    )

unavailable_rows = one_off_items_df["Availability"].eq("Not Available")
if not one_off_items_df.loc[unavailable_rows, "Value"].isna().all():
    validation_errors.append("Unavailable rows must have Value = NaN")

known_item = one_off_items_df.loc[
    (one_off_items_df["Fiscal Year"] == 2024)
    & (one_off_items_df["Category"] == "Unusual tax gains/losses")
]
if len(known_item) != 1:
    validation_errors.append("The 2024 unusual tax item must exist exactly once")
else:
    known_item = known_item.iloc[0]
    if known_item["Value"] != 10200:
        validation_errors.append("The 2024 unusual tax item value must be 10,200")
    if known_item["Direction"] != "Charge":
        validation_errors.append("The 2024 unusual tax item Direction must be Charge")
    if known_item["Tax Basis"] != "Tax item":
        validation_errors.append("The 2024 unusual tax item Tax Basis must be Tax item")

output_fields = [
    "Fiscal Year",
    "Category",
    "Description",
    "Value",
    "Direction",
    "Tax Basis",
    "Availability",
    "Source Detail",
]

print(one_off_items_df[output_fields].to_string(index=False))

available_items = one_off_items_df.loc[
    one_off_items_df["Availability"] == "Available", output_fields
]
print("\nAvailable one-off items:")
print(available_items.to_string(index=False))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("One-off item data structure validated successfully")
