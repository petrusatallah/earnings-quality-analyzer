import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd


project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
chart_directory = project_root / "charts"
chart_directory.mkdir(exist_ok=True)
matplotlib_cache = Path(tempfile.gettempdir()) / "earnings_quality_agent_matplotlib"
matplotlib_cache.mkdir(exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))

import matplotlib.pyplot as plt
from matplotlib.ticker import StrMethodFormatter

# The master table is the sole financial data source. Suppress its report while
# importing so this task prints only its own source table and status messages.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.master_analysis_table import master_analysis_df


REQUIRED_YEARS = [2022, 2023, 2024, 2025]
SOURCE_COLUMNS = ["Fiscal Year", "Net Income", "Operating Cash Flow"]

chart_data_df = (
    master_analysis_df[SOURCE_COLUMNS]
    .sort_values("Fiscal Year")
    .reset_index(drop=True)
    .copy()
)

print("NI vs OCF source data:")
print(chart_data_df.to_string(index=False))

figure, axis = plt.subplots(figsize=(9, 5.5))
net_income_line = axis.plot(
    chart_data_df["Fiscal Year"],
    chart_data_df["Net Income"],
    marker="o",
    label="Net Income",
)
ocf_line = axis.plot(
    chart_data_df["Fiscal Year"],
    chart_data_df["Operating Cash Flow"],
    marker="o",
    label="Operating Cash Flow",
)

axis.set_title("Net Income vs Operating Cash Flow\nApple Inc. | Fiscal Years 2022–2025")
axis.set_xlabel("Fiscal Year")
axis.set_ylabel("USD millions")
axis.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
axis.set_xticks(REQUIRED_YEARS)
axis.set_xticklabels([str(year) for year in REQUIRED_YEARS])
axis.grid(True)
axis.legend()
figure.tight_layout()

chart_path = chart_directory / "ni_vs_ocf.png"
figure.savefig(chart_path, dpi=300)

validation_errors = []
if len(chart_data_df) != 4:
    validation_errors.append("The chart must contain exactly four fiscal years")
if chart_data_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("The chart fiscal years must be 2022-2025 in ascending order")

source_by_year = master_analysis_df.set_index("Fiscal Year").sort_index()
plotted_by_year = chart_data_df.set_index("Fiscal Year")
for column in ["Net Income", "Operating Cash Flow"]:
    try:
        pd.testing.assert_series_equal(
            plotted_by_year[column],
            source_by_year.loc[REQUIRED_YEARS, column],
            check_names=False,
        )
    except AssertionError:
        validation_errors.append(f"{column} values do not match the master table")

lines = axis.get_lines()
if len(lines) != 2 or [line.get_label() for line in lines] != [
    "Net Income",
    "Operating Cash Flow",
]:
    validation_errors.append("The chart must contain exactly the two intended series")
if not chart_path.is_file():
    validation_errors.append("The chart PNG was not saved")
elif chart_path.stat().st_size == 0:
    validation_errors.append("The saved chart PNG is empty")

if validation_errors:
    raise ValueError(
        "NI vs OCF chart validation failed:\n- "
        + "\n- ".join(validation_errors)
    )

print("NI vs OCF chart saved successfully")
print(chart_path.relative_to(project_root).as_posix())
print("NI vs OCF chart validated successfully")

plt.show()
plt.close(figure)
