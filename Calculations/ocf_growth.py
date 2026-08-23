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


ocf_data = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"] == "Operating Cash Flow",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

calculation_records = []

for fiscal_year in [2023, 2024, 2025]:
    current_year_ocf = ocf_data.loc[fiscal_year]
    previous_year_ocf = ocf_data.loc[fiscal_year - 1]
    ocf_growth_result = (
        current_year_ocf - previous_year_ocf
    ) / previous_year_ocf

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "Current Year OCF": current_year_ocf,
            "Previous Year OCF": previous_year_ocf,
            "OCF Growth Formula": (
                f"({current_year_ocf:g} - {previous_year_ocf:g}) "
                f"/ {previous_year_ocf:g}"
            ),
            "OCF Growth Result": ocf_growth_result,
            "OCF Growth Percentage": f"{ocf_growth_result:.2%}",
        }
    )

ocf_growth_df = pd.DataFrame(calculation_records)
print(ocf_growth_df.to_string(index=False))

expected_results = {
    2023: -0.0950299219818094,
    2024: 0.06975566069312394,
    2025: -0.05726656180763441,
}
validation_tolerance = 1e-12

validation_passed = all(
    abs(row["OCF Growth Result"] - expected_results[row["Fiscal Year"]])
    <= validation_tolerance
    for row in calculation_records
)

if validation_passed:
    print("Operating Cash Flow growth calculations validated successfully")
else:
    print("Operating Cash Flow growth calculation validation failed")
