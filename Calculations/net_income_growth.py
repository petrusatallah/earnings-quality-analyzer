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


net_income_data = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"] == "Net Income",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

calculation_records = []

for fiscal_year in [2023, 2024, 2025]:
    current_year_net_income = net_income_data.loc[fiscal_year]
    previous_year_net_income = net_income_data.loc[fiscal_year - 1]
    ni_growth_result = (
        current_year_net_income - previous_year_net_income
    ) / previous_year_net_income

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "Current Year Net Income": current_year_net_income,
            "Previous Year Net Income": previous_year_net_income,
            "NI Growth Formula": (
                f"({current_year_net_income:g} - {previous_year_net_income:g}) "
                f"/ {previous_year_net_income:g}"
            ),
            "NI Growth Result": ni_growth_result,
            "NI Growth Percentage": f"{ni_growth_result:.2%}",
        }
    )

net_income_growth_df = pd.DataFrame(calculation_records)
print(net_income_growth_df.to_string(index=False))

expected_results = {
    2023: -0.028135426790777834,
    2024: -0.033599670086086914,
    2025: 0.19495177946573355,
}
validation_tolerance = 1e-12

validation_passed = all(
    abs(row["NI Growth Result"] - expected_results[row["Fiscal Year"]])
    <= validation_tolerance
    for row in calculation_records
)

if validation_passed:
    print("Net Income growth calculations validated successfully")
else:
    print("Net Income growth calculation validation failed")
