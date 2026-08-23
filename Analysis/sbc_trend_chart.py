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

# The validated master table is the sole source of chart data. Suppress its
# console report during import so this task prints only its own output.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.master_analysis_table import master_analysis_df


REQUIRED_YEARS = [2022, 2023, 2024, 2025]
SOURCE_COLUMNS = ["Fiscal Year", "Stock-Based Compensation"]

chart_data_df = (
    master_analysis_df.loc[
        master_analysis_df["Fiscal Year"].isin(REQUIRED_YEARS),
        SOURCE_COLUMNS,
    ]
    .sort_values("Fiscal Year")
    .reset_index(drop=True)
    .copy()
)

print("SBC trend source data:")
print(chart_data_df.to_string(index=False))

figure, axis = plt.subplots(figsize=(9, 5.5))
sbc_line = axis.plot(
    chart_data_df["Fiscal Year"],
    chart_data_df["Stock-Based Compensation"],
    marker="o",
    label="Stock-Based Compensation",
)[0]

axis.set_title(
    "Stock-Based Compensation Trend\n"
    "Apple Inc. | Fiscal Years 2022–2025"
)
axis.set_xlabel("Fiscal Year")
axis.set_ylabel("USD millions")
axis.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
axis.set_xticks(REQUIRED_YEARS)
axis.set_xticklabels([str(year) for year in REQUIRED_YEARS])
axis.grid(True)
axis.legend()
figure.tight_layout()

chart_path = chart_directory / "sbc_trend.png"
figure.savefig(chart_path, dpi=300)

validation_errors = []
if len(chart_data_df) != 4:
    validation_errors.append("The chart must contain exactly four fiscal years")
if chart_data_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("The chart fiscal years must be 2022-2025 in ascending order")

source_by_year = master_analysis_df.set_index("Fiscal Year").sort_index()
plotted_by_year = chart_data_df.set_index("Fiscal Year")
try:
    pd.testing.assert_series_equal(
        plotted_by_year["Stock-Based Compensation"],
        source_by_year.loc[REQUIRED_YEARS, "Stock-Based Compensation"],
        check_names=False,
    )
except AssertionError:
    validation_errors.append("SBC values do not match the master table")

expected_label = "Stock-Based Compensation"
if len(axis.get_lines()) != 1 or sbc_line.get_label() != expected_label:
    validation_errors.append("The chart must contain exactly the intended SBC series")

legend = axis.get_legend()
legend_labels = [] if legend is None else [text.get_text() for text in legend.get_texts()]
if legend_labels != [expected_label]:
    validation_errors.append("The legend must contain Stock-Based Compensation")
if not isinstance(axis.yaxis.get_major_formatter(), StrMethodFormatter):
    validation_errors.append("The Y-axis must use thousands-separated formatting")
if not chart_path.is_file():
    validation_errors.append("The chart PNG was not saved")
elif chart_path.stat().st_size == 0:
    validation_errors.append("The saved chart PNG is empty")

if validation_errors:
    raise ValueError(
        "SBC trend chart validation failed:\n- "
        + "\n- ".join(validation_errors)
    )

print("SBC trend chart saved successfully")
print(chart_path.relative_to(project_root).as_posix())
print("SBC trend chart validated successfully")

plt.show()
plt.close(figure)
