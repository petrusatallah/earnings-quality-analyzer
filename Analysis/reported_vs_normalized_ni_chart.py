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

# The validated master table is the sole source of financial data. Suppress its
# console report during import so this task prints only its own output.
with contextlib.redirect_stdout(io.StringIO()):
    from Analysis.master_analysis_table import master_analysis_df


REQUIRED_YEARS = [2022, 2023, 2024, 2025]
SOURCE_COLUMNS = [
    "Fiscal Year",
    "Reported Net Income",
    "Normalized Net Income",
    "Normalization Difference",
]

chart_data_df = (
    master_analysis_df.loc[
        master_analysis_df["Fiscal Year"].isin(REQUIRED_YEARS),
        SOURCE_COLUMNS,
    ]
    .sort_values("Fiscal Year")
    .reset_index(drop=True)
    .copy()
)

print("Reported vs Normalized NI source data:")
print(chart_data_df.to_string(index=False))

figure, axis = plt.subplots(figsize=(9, 5.5))
positions = list(range(len(chart_data_df)))
bar_width = 0.36
reported_positions = [position - bar_width / 2 for position in positions]
normalized_positions = [position + bar_width / 2 for position in positions]

reported_bars = axis.bar(
    reported_positions,
    chart_data_df["Reported Net Income"],
    width=bar_width,
    label="Reported Net Income",
)
normalized_bars = axis.bar(
    normalized_positions,
    chart_data_df["Normalized Net Income"],
    width=bar_width,
    label="Normalized Net Income",
)

axis.set_title(
    "Reported vs Normalized Net Income\n"
    "Apple Inc. | Fiscal Years 2022–2025"
)
axis.set_xlabel("Fiscal Year")
axis.set_ylabel("USD millions")
axis.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
axis.set_xticks(positions)
axis.set_xticklabels([str(year) for year in REQUIRED_YEARS])
axis.grid(True, axis="y")
axis.legend()
axis.set_ylim(
    bottom=20000,
    top=chart_data_df[
        ["Reported Net Income", "Normalized Net Income"]
    ].max().max() * 1.10,
)

annotation_years = []
for row_index, normalized_bar in enumerate(normalized_bars):
    reported_value = chart_data_df.loc[row_index, "Reported Net Income"]
    normalized_value = chart_data_df.loc[row_index, "Normalized Net Income"]
    display_difference = normalized_value - reported_value
    if display_difference != 0:
        fiscal_year = int(chart_data_df.loc[row_index, "Fiscal Year"])
        annotation_years.append(fiscal_year)
        axis.annotate(
            f"Difference: {display_difference:+,.0f}M",
            xy=(
                positions[row_index],
                normalized_bar.get_height(),
            ),
            xytext=(0, 22),
            textcoords="offset points",
            ha="center",
            va="bottom",
        )

figure.tight_layout()
chart_path = chart_directory / "reported_vs_normalized_ni.png"
figure.savefig(chart_path, dpi=300)

validation_errors = []
if len(chart_data_df) != 4:
    validation_errors.append("The chart must contain exactly four fiscal years")
if chart_data_df["Fiscal Year"].tolist() != REQUIRED_YEARS:
    validation_errors.append("The chart fiscal years must be 2022-2025 in ascending order")

source_by_year = master_analysis_df.set_index("Fiscal Year").sort_index()
plotted_by_year = chart_data_df.set_index("Fiscal Year")
for column in ["Reported Net Income", "Normalized Net Income"]:
    try:
        pd.testing.assert_series_equal(
            plotted_by_year[column],
            source_by_year.loc[REQUIRED_YEARS, column],
            check_names=False,
        )
    except AssertionError:
        validation_errors.append(f"{column} values do not match the master table")

bar_series = [reported_bars, normalized_bars]
expected_labels = ["Reported Net Income", "Normalized Net Income"]
if len(bar_series) != 2 or [bars.get_label() for bars in bar_series] != expected_labels:
    validation_errors.append("The chart must contain exactly the two intended bar series")
if any(len(bars) != 4 for bars in bar_series):
    validation_errors.append("Each grouped bar series must contain four annual bars")

legend = axis.get_legend()
legend_labels = [] if legend is None else [text.get_text() for text in legend.get_texts()]
if legend_labels != expected_labels:
    validation_errors.append("The legend must contain both intended income series")

differences_by_year = plotted_by_year["Normalization Difference"].to_dict()
if differences_by_year.get(2024) != 10200:
    validation_errors.append("The 2024 normalization difference must equal 10,200")
if any(differences_by_year.get(year) != 0 for year in [2022, 2023, 2025]):
    validation_errors.append("The 2022, 2023, and 2025 differences must equal zero")
expected_annotation_years = [
    year for year, difference in differences_by_year.items() if difference != 0
]
if annotation_years != expected_annotation_years or len(axis.texts) != len(annotation_years):
    validation_errors.append("Only non-zero normalization differences may be annotated")
if not isinstance(axis.yaxis.get_major_formatter(), StrMethodFormatter):
    validation_errors.append("The Y-axis must use thousands-separated formatting")
if not chart_path.is_file():
    validation_errors.append("The chart PNG was not saved")
elif chart_path.stat().st_size == 0:
    validation_errors.append("The saved chart PNG is empty")

if validation_errors:
    raise ValueError(
        "Reported vs Normalized NI chart validation failed:\n- "
        + "\n- ".join(validation_errors)
    )

axis.bar_label(reported_bars, fmt="{:,.0f}", padding=3)
axis.bar_label(normalized_bars, fmt="{:,.0f}", padding=3)
figure.tight_layout()
figure.savefig(chart_path, dpi=300)

print("Reported vs Normalized NI chart saved successfully")
print(chart_path.relative_to(project_root).as_posix())
print("Reported vs Normalized NI chart validated successfully")

plt.show()
plt.close(figure)
