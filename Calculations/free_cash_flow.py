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


required_years = [2022, 2023, 2024, 2025]
required_metrics = ["Operating Cash Flow", "Capital Expenditures"]

free_cash_flow_df = (
    apple_financial_data_df.loc[
        apple_financial_data_df["Metric"].isin(required_metrics),
        ["Fiscal Year", "Metric", "Value"],
    ]
    .pivot(index="Fiscal Year", columns="Metric", values="Value")
    .reindex(required_years)
    .reset_index()
)

free_cash_flow_df["Formula"] = free_cash_flow_df.apply(
    lambda row: (
        f'{row["Operating Cash Flow"]:g} - '
        f'{row["Capital Expenditures"]:g}'
    ),
    axis=1,
)
free_cash_flow_df["Free Cash Flow"] = (
    free_cash_flow_df["Operating Cash Flow"]
    - free_cash_flow_df["Capital Expenditures"]
)

free_cash_flow_df = free_cash_flow_df[
    [
        "Fiscal Year",
        "Operating Cash Flow",
        "Capital Expenditures",
        "Formula",
        "Free Cash Flow",
    ]
]

print(free_cash_flow_df.to_string(index=False))

validation_passed = (
    len(free_cash_flow_df) == 4
    and free_cash_flow_df["Fiscal Year"].tolist() == required_years
    and not free_cash_flow_df["Operating Cash Flow"].isna().any()
    and not free_cash_flow_df["Capital Expenditures"].isna().any()
    and not free_cash_flow_df["Free Cash Flow"].isna().any()
    and (
        free_cash_flow_df["Free Cash Flow"]
        == free_cash_flow_df["Operating Cash Flow"]
        - free_cash_flow_df["Capital Expenditures"]
    ).all()
)

if validation_passed:
    print("Free Cash Flow calculations validated successfully")
else:
    print("Free Cash Flow calculations validation failed")
