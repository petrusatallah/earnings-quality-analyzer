import contextlib
import io
import sys
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Suppress the Task 13 table and validation output during import.
with contextlib.redirect_stdout(io.StringIO()):
    from Calculations.working_capital_movements import (
        working_capital_movements_df,
    )


required_years = [2023, 2024, 2025]

changes_by_year = working_capital_movements_df.pivot(
    index="Fiscal Year", columns="Metric", values="Change"
).reindex(required_years)


def classify_cash_effect(value):
    """Return the proxy's sign bucket, not a reported cash-flow-statement result."""
    if value > 0:
        return "Cash Benefit"
    if value < 0:
        return "Cash Use"
    return "No Cash Effect"


calculation_records = []

for fiscal_year, changes in changes_by_year.iterrows():
    ar_change = changes["Accounts Receivable"]
    inventory_change = changes["Inventory"]
    ap_change = changes["Accounts Payable"]
    net_cash_effect = -ar_change - inventory_change + ap_change

    classification = classify_cash_effect(net_cash_effect)
    if classification == "Cash Benefit":
        proxy_classification = (
            "Selected-account working-capital proxy suggests a cash benefit"
        )
    elif classification == "Cash Use":
        proxy_classification = (
            "Selected-account working-capital proxy suggests a cash use"
        )
    else:
        proxy_classification = (
            "Selected-account working-capital proxy suggests no cash use or benefit"
        )

    calculation_records.append(
        {
            "Fiscal Year": fiscal_year,
            "AR Change": ar_change,
            "Inventory Change": inventory_change,
            "AP Change": ap_change,
            "Net Working-Capital Cash Effect": net_cash_effect,
            "Net Cash Classification": proxy_classification,
            "Formula": (
                f"-{ar_change:g} - {inventory_change:g} + {ap_change:g}"
            ),
        }
    )

working_capital_analysis_df = pd.DataFrame(calculation_records)

print(working_capital_analysis_df.to_string(index=False))


calculated_net_effect = (
    -working_capital_analysis_df["AR Change"]
    - working_capital_analysis_df["Inventory Change"]
    + working_capital_analysis_df["AP Change"]
)

validation_passed = (
    len(working_capital_analysis_df) == 3
    and working_capital_analysis_df["Fiscal Year"].tolist() == required_years
    and not working_capital_analysis_df[
        ["AR Change", "Inventory Change", "AP Change"]
    ].isna().any().any()
    and (
        working_capital_analysis_df["Net Working-Capital Cash Effect"]
        == calculated_net_effect
    ).all()
    and all(
        row["Net Cash Classification"]
        == {
            "Cash Benefit": (
                "Selected-account working-capital proxy suggests a cash benefit"
            ),
            "Cash Use": (
                "Selected-account working-capital proxy suggests a cash use"
            ),
            "No Cash Effect": (
                "Selected-account working-capital proxy suggests no cash use or benefit"
            ),
        }[classify_cash_effect(row["Net Working-Capital Cash Effect"])]
        for _, row in working_capital_analysis_df.iterrows()
    )
)

if validation_passed:
    print("Working capital analysis table validated successfully")
else:
    print("Working capital analysis table validation failed")
