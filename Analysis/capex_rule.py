import contextlib
import io
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress the Task 11 table and validation output during import.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.capex_analysis import capex_analysis_df


required_years = [2022, 2023, 2024, 2025]
rule_threshold = 1.20
exact_rule = "CapEx / D&A >= 1.20x"

capex_rule_df = capex_analysis_df[
    ["Fiscal Year", "CapEx", "D&A", "CapEx / D&A", "CapEx / D&A Display"]
].copy()

capex_rule_df["Exact Rule"] = exact_rule
capex_rule_df["Status"] = capex_rule_df["CapEx / D&A"].map(
    lambda ratio: (
        "Needs investigation"
        if ratio >= rule_threshold
        else "No investigation triggered"
    )
)

print(capex_rule_df.to_string(index=False))

expected_statuses = {
    2022: "No investigation triggered",
    2023: "No investigation triggered",
    2024: "No investigation triggered",
    2025: "No investigation triggered",
}

validation_passed = (
    len(capex_rule_df) == 4
    and capex_rule_df["Fiscal Year"].tolist() == required_years
    and not capex_rule_df[
        ["CapEx", "D&A", "CapEx / D&A", "CapEx / D&A Display"]
    ].isna().any().any()
    and (capex_rule_df["Exact Rule"] == exact_rule).all()
    and all(
        row["Status"] == expected_statuses[row["Fiscal Year"]]
        for _, row in capex_rule_df.iterrows()
    )
    and all(
        row["Status"]
        == (
            "Needs investigation"
            if row["CapEx / D&A"] >= rule_threshold
            else "No investigation triggered"
        )
        for _, row in capex_rule_df.iterrows()
    )
)

if validation_passed:
    print("CapEx analyst rule validated successfully")
else:
    print("CapEx analyst rule validation failed")
