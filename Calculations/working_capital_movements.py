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


required_years = [2023, 2024, 2025]
required_metrics = [
    "Accounts Receivable",
    "Inventory",
    "Accounts Payable",
]

working_capital_data = apple_financial_data_df.loc[
    apple_financial_data_df["Metric"].isin(required_metrics),
    ["Fiscal Year", "Metric", "Value"],
]

metric_values = working_capital_data.pivot(
    index="Fiscal Year", columns="Metric", values="Value"
).sort_index()

calculation_records = []

for fiscal_year in required_years:
    for metric in required_metrics:
        current_year_value = metric_values.loc[fiscal_year, metric]
        previous_year_value = metric_values.loc[fiscal_year - 1, metric]
        change = current_year_value - previous_year_value

        if change > 0:
            direction = "Increase"
        elif change < 0:
            direction = "Decrease"
        else:
            direction = "No Change"

        if direction == "No Change":
            cash_classification = "No Cash Effect"
        elif metric in ["Accounts Receivable", "Inventory"]:
            cash_classification = (
                "Cash Use" if direction == "Increase" else "Cash Benefit"
            )
        else:
            cash_classification = (
                "Cash Benefit" if direction == "Increase" else "Cash Use"
            )

        calculation_records.append(
            {
                "Fiscal Year": fiscal_year,
                "Metric": metric,
                "Current Year Value": current_year_value,
                "Previous Year Value": previous_year_value,
                "Change": change,
                "Direction": direction,
                "Cash Classification": cash_classification,
            }
        )

working_capital_movements_df = pd.DataFrame(calculation_records)

print(working_capital_movements_df.to_string(index=False))


def expected_cash_classification(metric, change):
    if change == 0:
        return "No Cash Effect"
    if metric in ["Accounts Receivable", "Inventory"]:
        return "Cash Use" if change > 0 else "Cash Benefit"
    return "Cash Benefit" if change > 0 else "Cash Use"


validation_passed = (
    len(working_capital_movements_df) == 9
    and sorted(working_capital_movements_df["Fiscal Year"].unique().tolist())
    == required_years
    and all(
        set(
            working_capital_movements_df.loc[
                working_capital_movements_df["Fiscal Year"] == fiscal_year,
                "Metric",
            ]
        )
        == set(required_metrics)
        for fiscal_year in required_years
    )
    and not working_capital_movements_df["Current Year Value"].isna().any()
    and not working_capital_movements_df["Previous Year Value"].isna().any()
    and (
        working_capital_movements_df["Change"]
        == working_capital_movements_df["Current Year Value"]
        - working_capital_movements_df["Previous Year Value"]
    ).all()
    and all(
        row["Cash Classification"]
        == expected_cash_classification(row["Metric"], row["Change"])
        for _, row in working_capital_movements_df.iterrows()
    )
)

if validation_passed:
    print("Working capital movement calculations validated successfully")
else:
    print("Working capital movement calculations validation failed")
