import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Task 27 prints its calculation tables when imported. Suppress that output so
# this module prints only the reported-versus-normalized comparison.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.normalized_net_income import normalized_net_income_df


required_years = [2022, 2023, 2024, 2025]
zero_tolerance = 1e-12

reported_vs_normalized_earnings_df = normalized_net_income_df[
    ["Fiscal Year", "Reported Net Income", "Normalized Net Income"]
].copy()

reported_vs_normalized_earnings_df["Difference"] = (
    reported_vs_normalized_earnings_df["Normalized Net Income"]
    - reported_vs_normalized_earnings_df["Reported Net Income"]
)

reported_ni_denominator = reported_vs_normalized_earnings_df[
    "Reported Net Income"
].abs()
reported_vs_normalized_earnings_df["Percentage Difference"] = (
    reported_vs_normalized_earnings_df["Difference"]
    / reported_ni_denominator.where(reported_ni_denominator != 0)
)
reported_vs_normalized_earnings_df["Percentage Difference Display"] = (
    reported_vs_normalized_earnings_df["Percentage Difference"].map(
        lambda value: "N/A" if pd.isna(value) else f"{value:.2%}"
    )
)


def classify_adjustment_direction(difference):
    if abs(difference) <= zero_tolerance:
        return "No difference"
    if difference > 0:
        return "Normalized earnings higher"
    return "Normalized earnings lower"


reported_vs_normalized_earnings_df["Earnings Adjustment Direction"] = (
    reported_vs_normalized_earnings_df["Difference"].map(
        classify_adjustment_direction
    )
)


validation_errors = []

if len(reported_vs_normalized_earnings_df) != 4:
    validation_errors.append("Expected exactly four fiscal-year rows")

if reported_vs_normalized_earnings_df["Fiscal Year"].tolist() != required_years:
    validation_errors.append("Fiscal years must be exactly 2022, 2023, 2024, 2025")

task_27_values = normalized_net_income_df.set_index("Fiscal Year")
comparison_values = reported_vs_normalized_earnings_df.set_index("Fiscal Year")

if not comparison_values["Reported Net Income"].equals(
    task_27_values["Reported Net Income"]
):
    validation_errors.append("Reported Net Income does not match Task 27")

if not comparison_values["Normalized Net Income"].equals(
    task_27_values["Normalized Net Income"]
):
    validation_errors.append("Normalized Net Income does not match Task 27")

expected_differences = {2022: 0, 2023: 0, 2024: 10200, 2025: 0}
for fiscal_year, expected_difference in expected_differences.items():
    if (
        abs(comparison_values.loc[fiscal_year, "Difference"] - expected_difference)
        > zero_tolerance
    ):
        validation_errors.append(
            f"The {fiscal_year} Difference must be {expected_difference:,}"
        )

expected_2024_percentage = 10200 / abs(
    comparison_values.loc[2024, "Reported Net Income"]
)
actual_2024_percentage = comparison_values.loc[2024, "Percentage Difference"]
if abs(actual_2024_percentage - expected_2024_percentage) > zero_tolerance:
    validation_errors.append("The 2024 Percentage Difference must be about 10.88%")

expected_directions = {
    2022: "No difference",
    2023: "No difference",
    2024: "Normalized earnings higher",
    2025: "No difference",
}
actual_directions = comparison_values["Earnings Adjustment Direction"].to_dict()
if actual_directions != expected_directions:
    validation_errors.append("Earnings Adjustment Direction values are incorrect")

print(reported_vs_normalized_earnings_df.to_string(index=False))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Reported vs Normalized Earnings validated successfully")
