import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Task 30 remains the authoritative source for every underlying rule result.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.red_flag_table import red_flag_table_df


SEVERITY_MAPPING = {
    "None": "Low Risk",
    "Low": "Needs Investigation",
    "Medium": "Needs Investigation",
    "High": "Material Concern",
    "Unavailable": "Unavailable",
}
FINAL_SEVERITIES = {
    "Low Risk",
    "Needs Investigation",
    "Material Concern",
    "Unavailable",
}
FINAL_PRIORITY = {
    "Low Risk": 0,
    "Needs Investigation": 1,
    "Material Concern": 2,
}

SEVERITY_MEANINGS = {
    "Low Risk": (
        "No material predefined earnings-quality signal currently requires "
        "investigation under the implemented rules."
    ),
    "Needs Investigation": (
        "One or more predefined earnings-quality signals or review conditions "
        "require analyst investigation."
    ),
    "Material Concern": (
        "Multiple or stronger predefined earnings-quality signals are present "
        "under the existing rules and require heightened investigation."
    ),
}


detailed_severity_table_df = red_flag_table_df[
    [
        "Fiscal Year",
        "Metric",
        "Result",
        "Internal Severity",
        "Final Severity",
        "Explanation",
    ]
].copy(deep=True)
detailed_severity_table_df = detailed_severity_table_df[
    [
        "Fiscal Year",
        "Metric",
        "Result",
        "Internal Severity",
        "Final Severity",
        "Explanation",
    ]
]


fiscal_year_rows = []
for fiscal_year, year_rows in detailed_severity_table_df.groupby(
    "Fiscal Year", sort=True
):
    available_severities = [
        severity
        for severity in year_rows["Final Severity"]
        if severity in FINAL_PRIORITY
    ]
    strongest_available = (
        max(available_severities, key=FINAL_PRIORITY.get)
        if available_severities
        else "Unavailable"
    )
    has_unavailable = year_rows["Final Severity"].eq("Unavailable").any()
    high_level_severity = (
        "Unavailable"
        if has_unavailable and strongest_available == "Low Risk"
        else strongest_available
    )
    triggered_metrics = year_rows.loc[
        year_rows["Result"].isin(("Flag", "Review")), "Metric"
    ].tolist()
    unavailable_metrics = year_rows.loc[
        year_rows["Result"].eq("Unavailable"), "Metric"
    ].tolist()
    fiscal_year_rows.append(
        {
            "Fiscal Year": int(fiscal_year),
            "High-Level Severity": high_level_severity,
            "Material Concern Count": int(
                year_rows["Final Severity"].eq("Material Concern").sum()
            ),
            "Needs Investigation Count": int(
                year_rows["Final Severity"].eq("Needs Investigation").sum()
            ),
            "Low Risk Count": int(
                year_rows["Final Severity"].eq("Low Risk").sum()
            ),
            "Unavailable Count": int(
                year_rows["Final Severity"].eq("Unavailable").sum()
            ),
            "Triggered Metrics": (
                "; ".join(triggered_metrics) if triggered_metrics else "None"
            ),
            "Unavailable Metrics": (
                "; ".join(unavailable_metrics) if unavailable_metrics else "None"
            ),
            "Explanation": (
                "Some rule results are unavailable because independently reviewed "
                "evidence is missing. Available concerns retain their existing "
                "severity; missing evidence is not treated as No Flag or Low Risk."
                if has_unavailable
                else SEVERITY_MEANINGS[high_level_severity]
            ),
        }
    )


fiscal_year_severity_summary_df = pd.DataFrame(fiscal_year_rows)
available_benchmark_severities = [
    severity
    for severity in fiscal_year_severity_summary_df["High-Level Severity"]
    if severity in FINAL_PRIORITY
]
strongest_benchmark_severity = (
    max(available_benchmark_severities, key=FINAL_PRIORITY.get)
    if available_benchmark_severities
    else "Unavailable"
)
has_unavailable_evidence = fiscal_year_severity_summary_df[
    "Unavailable Count"
].gt(0).any()
benchmark_severity = (
    "Unavailable"
    if has_unavailable_evidence and strongest_benchmark_severity == "Low Risk"
    else strongest_benchmark_severity
)
benchmark_explanation = {
    "Material Concern": (
        "At least one analyzed fiscal year contains stronger combined "
        "earnings-quality signals under the existing predefined rules; heightened "
        "analyst investigation is required."
    ),
    "Needs Investigation": (
        "At least one analyzed fiscal year contains predefined earnings-quality "
        "signals or review conditions requiring analyst investigation."
    ),
    "Low Risk": SEVERITY_MEANINGS["Low Risk"],
    "Unavailable": (
        "Overall severity is unavailable because no analyzed rule has sufficient "
        "evidence."
    ),
}[benchmark_severity]
if has_unavailable_evidence:
    benchmark_explanation = (
        "Some evidence is unavailable. Available concerns retain their existing "
        "severity, but missing evidence is not classified as No Flag or Low Risk."
    )
benchmark_severity_df = pd.DataFrame(
    [
        {
            "Benchmark Severity": benchmark_severity,
            "Availability": (
                "Partial" if has_unavailable_evidence else "Complete"
            ),
            "Explanation": benchmark_explanation,
        }
    ]
)


validation_errors = []
if SEVERITY_MAPPING != {
    "None": "Low Risk",
    "Low": "Needs Investigation",
    "Medium": "Needs Investigation",
    "High": "Material Concern",
    "Unavailable": "Unavailable",
}:
    validation_errors.append("The internal-to-final severity mapping was changed")
if not set(detailed_severity_table_df["Final Severity"]).issubset(
    FINAL_SEVERITIES
):
    validation_errors.append("An unapproved final severity was used")

source_fields = red_flag_table_df[
    ["Fiscal Year", "Metric", "Result", "Severity", "Explanation"]
].reset_index(drop=True)
reused_fields = detailed_severity_table_df[
    ["Fiscal Year", "Metric", "Result", "Internal Severity", "Explanation"]
].rename(columns={"Internal Severity": "Severity"}).reset_index(drop=True)
try:
    pd.testing.assert_frame_equal(reused_fields, source_fields)
except AssertionError:
    validation_errors.append("Task 30 results were not reused unchanged")

if len(detailed_severity_table_df) != len(red_flag_table_df):
    validation_errors.append("Detailed output must retain every Task 30 row")
expected_year_severities = {
    2023: "Needs Investigation",
    2024: "Needs Investigation",
    2025: "Material Concern",
}
actual_year_severities = fiscal_year_severity_summary_df.set_index(
    "Fiscal Year"
)["High-Level Severity"].to_dict()
if actual_year_severities != expected_year_severities:
    validation_errors.append("Apple fiscal-year severities are unexpected")
if benchmark_severity != "Material Concern":
    validation_errors.append("Benchmark Severity must be Material Concern")
all_output_columns = (
    list(detailed_severity_table_df.columns)
    + list(fiscal_year_severity_summary_df.columns)
    + list(benchmark_severity_df.columns)
)
if any("score" in column.lower() for column in all_output_columns):
    validation_errors.append("The severity system must not create a score")

print("Detailed severity table:")
print(detailed_severity_table_df.to_string(index=False))
print("\nFiscal-year severity summary:")
print(fiscal_year_severity_summary_df.to_string(index=False))
print("\nBenchmark severity:")
print(benchmark_severity_df.to_string(index=False))

if validation_errors:
    for error in validation_errors:
        print(error)
else:
    print("Severity system validated successfully")
