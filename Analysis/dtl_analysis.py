import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress the existing dataset's output during import so this module prints
# only the DTL analysis table and validation result.
with contextlib.redirect_stdout(io.StringIO()):
    from Data.deferred_tax_data import deferred_tax_data_df


required_years = [2022, 2023, 2024, 2025]
zero_tolerance = 1e-12

dtl_by_year = (
    deferred_tax_data_df.loc[
        deferred_tax_data_df["Metric"] == "Deferred Tax Liabilities",
        ["Fiscal Year", "Value"],
    ]
    .set_index("Fiscal Year")["Value"]
    .sort_index()
)

calculation_records = []

for fiscal_year in required_years:
    dtl = dtl_by_year.loc[fiscal_year]

    if fiscal_year == required_years[0]:
        dtl_growth = None
        direction = "N/A"
        interpretation = "Insufficient prior-year data"
    else:
        previous_dtl = dtl_by_year.loc[fiscal_year - 1]
        dtl_growth = (dtl - previous_dtl) / previous_dtl

        if abs(dtl_growth) <= zero_tolerance:
            direction = "No change"
            interpretation = (
                "DTL unchanged; source details required before interpretation"
            )
        elif dtl_growth > 0:
            direction = "Rising"
            interpretation = (
                "DTL increased; source details required before interpretation"
            )
        else:
            direction = "Falling"
            interpretation = (
                "DTL decreased; source details required before interpretation"
            )

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "DTL": dtl,
            "DTL Growth": dtl_growth,
            "DTL Growth Percentage": (
                "N/A" if dtl_growth is None else f"{dtl_growth:.2%}"
            ),
            "Direction": direction,
            "Interpretation": interpretation,
        }
    )

dtl_analysis_df = pd.DataFrame(calculation_records)

print(dtl_analysis_df.to_string(index=False))

expected_directions = {
    2022: "N/A",
    2023: "Rising",
    2024: "Falling",
    2025: "Rising",
}

dtl_values_match_source = all(
    row["DTL"] == dtl_by_year.loc[row["Fiscal Year"]]
    for _, row in dtl_analysis_df.iterrows()
)

directions_match_expected = all(
    row["Direction"] == expected_directions[row["Fiscal Year"]]
    for _, row in dtl_analysis_df.iterrows()
)

validation_passed = (
    len(dtl_analysis_df) == 4
    and dtl_analysis_df["Fiscal Year"].tolist() == required_years
    and pd.isna(dtl_analysis_df.loc[0, "DTL Growth"])
    and dtl_values_match_source
    and directions_match_expected
)

if validation_passed:
    print("DTL analysis validated successfully")
else:
    print("DTL analysis validation failed")
