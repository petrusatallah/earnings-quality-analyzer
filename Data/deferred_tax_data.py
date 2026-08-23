from contextlib import redirect_stdout
from io import StringIO

import pandas as pd


# The verified benchmark prints when imported. Suppress that output so this module
# prints only the dedicated deferred-tax table and its validation result.
with redirect_stdout(StringIO()):
    try:
        from Data.apple_test_dataset import apple_financial_data_df
    except ModuleNotFoundError:
        from apple_test_dataset import apple_financial_data_df


required_fields = [
    "Company",
    "Ticker",
    "Fiscal Year",
    "Metric",
    "Value",
    "Units",
    "Financial Statement",
    "Source",
    "Source Date",
    "Availability",
]

required_years = [2022, 2023, 2024, 2025]
required_metrics = [
    "Deferred Tax Assets",
    "Deferred Tax Liabilities",
    "Current Tax Expense",
    "Deferred Tax Expense",
    "Tax-Loss Carryforwards",
]

# Consolidated current and deferred provisions reported in Apple's income tax
# note. These remain separate from the benchmark's total Tax Expense records.
tax_expense_values = {
    2022: {"Current Tax Expense": 18405, "Deferred Tax Expense": 895},
    2023: {"Current Tax Expense": 19765, "Deferred Tax Expense": -3024},
    2024: {"Current Tax Expense": 32780, "Deferred Tax Expense": -3031},
    2025: {"Current Tax Expense": 22058, "Deferred Tax Expense": -1339},
}

dta_dtl_metrics = {"Deferred Tax Assets", "Deferred Tax Liabilities"}
benchmark_tax_records = apple_financial_data_df.loc[
    apple_financial_data_df["Metric"].isin(dta_dtl_metrics)
    & apple_financial_data_df["Fiscal Year"].isin(required_years)
].copy()

deferred_tax_data = []

for fiscal_year in required_years:
    for metric in ("Deferred Tax Assets", "Deferred Tax Liabilities"):
        benchmark_record = benchmark_tax_records.loc[
            (benchmark_tax_records["Fiscal Year"] == fiscal_year)
            & (benchmark_tax_records["Metric"] == metric)
        ].iloc[0]
        record = benchmark_record.to_dict()
        record["Financial Statement"] = "Income Tax Note"
        record["Availability"] = "Available"
        deferred_tax_data.append(record)

    for metric in ("Current Tax Expense", "Deferred Tax Expense"):
        deferred_tax_data.append(
            {
                "Company": "Apple Inc.",
                "Ticker": "AAPL",
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Value": tax_expense_values[fiscal_year][metric],
                "Units": "USD millions",
                "Financial Statement": "Income Tax Note",
                "Source": "Apple Form 10-K",
                "Source Date": benchmark_tax_records.loc[
                    benchmark_tax_records["Fiscal Year"] == fiscal_year,
                    "Source Date",
                ].iloc[0],
                "Availability": "Available",
            }
        )

    # Apple reports tax-credit carryforwards, not a comparable tax-loss
    # carryforward amount. Tax credits must not be substituted here.
    deferred_tax_data.append(
        {
            "Company": "Apple Inc.",
            "Ticker": "AAPL",
            "Fiscal Year": fiscal_year,
            "Metric": "Tax-Loss Carryforwards",
            "Value": None,
            "Units": "USD millions",
            "Financial Statement": "Income Tax Note",
            "Source": "Apple Form 10-K",
            "Source Date": benchmark_tax_records.loc[
                benchmark_tax_records["Fiscal Year"] == fiscal_year,
                "Source Date",
            ].iloc[0],
            "Availability": "Not Available",
        }
    )

deferred_tax_data_df = pd.DataFrame(deferred_tax_data, columns=required_fields)


validation_errors = []

if len(deferred_tax_data_df) != 20:
    validation_errors.append(
        f"Expected exactly 20 rows, found {len(deferred_tax_data_df)}"
    )

if set(deferred_tax_data_df["Fiscal Year"]) != set(required_years):
    validation_errors.append("Fiscal years must be exactly 2022, 2023, 2024, 2025")

for fiscal_year in required_years:
    year_metrics = deferred_tax_data_df.loc[
        deferred_tax_data_df["Fiscal Year"] == fiscal_year, "Metric"
    ]
    if len(year_metrics) != len(required_metrics) or set(year_metrics) != set(
        required_metrics
    ):
        validation_errors.append(
            f"Required tax metrics are incomplete or duplicated for {fiscal_year}"
        )

for _, benchmark_record in benchmark_tax_records.iterrows():
    imported_value = deferred_tax_data_df.loc[
        (deferred_tax_data_df["Fiscal Year"] == benchmark_record["Fiscal Year"])
        & (deferred_tax_data_df["Metric"] == benchmark_record["Metric"]),
        "Value",
    ].iloc[0]
    if imported_value != benchmark_record["Value"]:
        validation_errors.append(
            f"{benchmark_record['Metric']} does not match the benchmark for "
            f"{benchmark_record['Fiscal Year']}"
        )

missing_values = deferred_tax_data_df["Value"].isna()
if not (
    deferred_tax_data_df.loc[missing_values, "Availability"] == "Not Available"
).all():
    validation_errors.append(
        "Missing values are allowed only when Availability is Not Available"
    )

carryforwards = deferred_tax_data_df[
    deferred_tax_data_df["Metric"] == "Tax-Loss Carryforwards"
]
if not (
    carryforwards["Value"].isna()
    & carryforwards["Availability"].eq("Not Available")
).all():
    validation_errors.append("Tax-loss carryforward values must not be invented")

invalid_availability = set(deferred_tax_data_df["Availability"]) - {
    "Available",
    "Not Available",
}
if invalid_availability:
    validation_errors.append(
        f"Invalid Availability values: {sorted(invalid_availability)}"
    )

print(
    deferred_tax_data_df[
        ["Fiscal Year", "Metric", "Value", "Units", "Availability", "Source"]
    ].to_string(index=False)
)

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Deferred tax data structure validated successfully")
