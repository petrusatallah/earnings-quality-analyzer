import contextlib
import io
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress the individual calculation tables printed during import.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.ar_growth import ar_growth_df
    from Calculations.net_income_growth import net_income_growth_df
    from Calculations.ocf_growth import ocf_growth_df
    from Calculations.revenue_growth import revenue_growth_df


comparison_df = (
    revenue_growth_df[["Fiscal Year", "Result"]]
    .rename(columns={"Result": "Revenue Growth"})
    .merge(
        ar_growth_df[["Fiscal Year", "AR Growth Result"]].rename(
            columns={"AR Growth Result": "AR Growth"}
        ),
        on="Fiscal Year",
    )
    .merge(
        net_income_growth_df[["Fiscal Year", "NI Growth Result"]].rename(
            columns={"NI Growth Result": "Net Income Growth"}
        ),
        on="Fiscal Year",
    )
    .merge(
        ocf_growth_df[["Fiscal Year", "OCF Growth Result"]].rename(
            columns={"OCF Growth Result": "OCF Growth"}
        ),
        on="Fiscal Year",
    )
    .sort_values("Fiscal Year")
    .reset_index(drop=True)
)

growth_columns = [
    "Revenue Growth",
    "AR Growth",
    "Net Income Growth",
    "OCF Growth",
]

print_table = comparison_df.copy()
for column in growth_columns:
    print_table[column] = print_table[column].map(lambda value: f"{value:.2%}")

print(print_table.to_string(index=False))

expected_years = [2023, 2024, 2025]
has_three_rows = len(comparison_df) == 3
has_expected_years = comparison_df["Fiscal Year"].tolist() == expected_years
has_no_missing_growth_values = not comparison_df[growth_columns].isna().any().any()

if has_three_rows and has_expected_years and has_no_missing_growth_values:
    print("Accrual vs cash comparison table validated successfully")
else:
    print("Accrual vs cash comparison table validation failed")
