import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress verification output produced by the existing modules during import.
with contextlib.redirect_stdout(io.StringIO()):
    from Data.apple_test_dataset import apple_financial_data_df
    from Calculations.revenue_growth import revenue_growth_df


ar_data = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"] == "Accounts Receivable",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

revenue_growth_by_year = revenue_growth_df.set_index("Fiscal Year")["Result"]
calculation_records = []

for fiscal_year in [2023, 2024, 2025]:
    current_year_ar = ar_data.loc[fiscal_year]
    previous_year_ar = ar_data.loc[fiscal_year - 1]
    ar_growth_result = (current_year_ar - previous_year_ar) / previous_year_ar
    revenue_growth_result = revenue_growth_by_year.loc[fiscal_year]
    difference = ar_growth_result - revenue_growth_result

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "Current Year AR": current_year_ar,
            "Previous Year AR": previous_year_ar,
            "AR Growth Formula": (
                f"({current_year_ar:g} - {previous_year_ar:g}) "
                f"/ {previous_year_ar:g}"
            ),
            "AR Growth Result": ar_growth_result,
            "AR Growth Percentage": f"{ar_growth_result:.2%}",
            "Revenue Growth Result": revenue_growth_result,
            "Revenue Growth Percentage": f"{revenue_growth_result:.2%}",
            "Difference: AR Growth minus Revenue Growth": difference,
        }
    )

ar_growth_df = pd.DataFrame(calculation_records)
print(ar_growth_df.to_string(index=False))

expected_results = {
    2023: 0.04697700823162078,
    2024: 0.13223532601328453,
    2025: 0.1905716851242143,
}
validation_tolerance = 1e-12

validation_passed = all(
    abs(row["AR Growth Result"] - expected_results[row["Fiscal Year"]])
    <= validation_tolerance
    for row in calculation_records
)

if validation_passed:
    print("Accounts Receivable growth calculations validated successfully")
else:
    print("Accounts Receivable growth calculation validation failed")
