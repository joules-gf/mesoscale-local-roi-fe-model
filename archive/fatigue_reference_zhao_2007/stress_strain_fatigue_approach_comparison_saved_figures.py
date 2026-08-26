import os
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator


# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "fatigue_AA7075-T651_Zhao_2007.csv"
FIGURE_DIR = SCRIPT_DIR / "fatigue_figures"
FIGURE_DIR.mkdir(exist_ok=True)


# -----------------------------------------------------------------------------
# Import data
# -----------------------------------------------------------------------------
df = pd.read_csv(DATA_FILE, header=0)
df.columns = df.columns.str.strip()

# Clean column names / values that are used for plotting
for column in ["Nf_cycles", "stress_amplitude_MPa"]:
    df[column] = pd.to_numeric(df[column], errors="coerce")

df["specimen"] = df["specimen"].astype(str).str.strip()

# Make failed robust to Boolean values, strings, and numeric 0/1 values.
# This fixes the common issue where df["failed"] == False returns no rows
# because the CSV stored False as the string "False".
failed_clean = df["failed"]

if failed_clean.dtype == bool:
    df["failed_bool"] = failed_clean
else:
    df["failed_bool"] = (
        failed_clean.astype(str)
        .str.strip()
        .str.lower()
        .map({
            "true": True,
            "t": True,
            "yes": True,
            "y": True,
            "1": True,
            "false": False,
            "f": False,
            "no": False,
            "n": False,
            "0": False,
        })
    )

# Keep only rows with usable plotting data
plot_df = df.dropna(subset=["Nf_cycles", "stress_amplitude_MPa", "failed_bool"]).copy()
plot_df = plot_df[(plot_df["Nf_cycles"] > 0) & (plot_df["stress_amplitude_MPa"] > 0)]

# Get the two specimen types
specimen_types = plot_df["specimen"].dropna().unique()

if len(specimen_types) != 2:
    raise ValueError(
        f"Expected exactly two specimen types, but found {len(specimen_types)}: "
        f"{specimen_types}"
    )

specimen_1 = specimen_types[0]
specimen_2 = specimen_types[1]


# -----------------------------------------------------------------------------
# Plot helpers
# -----------------------------------------------------------------------------
def plot_specimen_markers(ax, data, x_column):
    """Plot the two specimen types with customized markers."""
    group_1 = data[data["specimen"] == specimen_1]
    group_2 = data[data["specimen"] == specimen_2]

    ax.scatter(
        group_1[x_column],
        group_1["stress_amplitude_MPa"],
        marker="o",
        facecolors="none",
        edgecolors="red",
        label=specimen_1,
        zorder=3,
    )

    ax.scatter(
        group_2[x_column],
        group_2["stress_amplitude_MPa"],
        marker="d",
        facecolors="green",
        edgecolors="green",
        label=specimen_2,
        zorder=3,
    )


def add_runout_arrows(ax, data, x_column):
    """Add a right arrow next to every marker where failed is False."""
    runout_data = data[data["failed_bool"] == False]

    # Text annotations are more reliable than a scatter marker for arrows because
    # they remain visible under linear/log axes and can be offset in screen units.
    for _, row in runout_data.iterrows():
        ax.annotate(
            "→",
            xy=(row[x_column], row["stress_amplitude_MPa"]),
            xytext=(2, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=12,
            color="black",
            zorder=4,
        )

    # Dummy artist so the arrow appears once in the legend
    ax.scatter(
        [],
        [],
        marker=r"$\rightarrow$",
        color="black",
        s=100,
        label="Runout / did not fail",
    )


def format_log10_x_ticks(ax):
    """
    Use a linear x-axis whose coordinate is log10(N),
    but label ticks as powers of 10.
    """
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _: rf"$10^{{{int(value)}}}$")
    )


def finish_and_save(fig, ax, filename, x_label):
    ax.set_xlabel(x_label)
    ax.set_ylabel("Stress amplitude [MPa]")
    ax.grid(True, which="both", alpha=0.35)
    ax.legend()
    fig.tight_layout()

    png_path = FIGURE_DIR / f"{filename}.png"

    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {png_path}")

# -----------------------------------------------------------------------------
# Figure 1: log-log plot
# x-axis: log(Nf), y-axis: log(stress amplitude)
# -----------------------------------------------------------------------------
fig, ax = plt.subplots()
plot_specimen_markers(ax, plot_df, x_column="Nf_cycles")
add_runout_arrows(ax, plot_df, x_column="Nf_cycles")
ax.set_xscale("log")
ax.set_yscale("log")
finish_and_save(
    fig,
    ax,
    filename="AA7075_T651_SN_loglog",
    x_label="Cycles to failure, N",
)


# -----------------------------------------------------------------------------
# Figure 2: y-axis log only; x-axis linear in log10(N)
# x-axis values are log10(N), but tick labels are shown as 10^x.
# -----------------------------------------------------------------------------
plot_df_logx = plot_df.copy()
plot_df_logx["log10_Nf_cycles"] = np.log10(plot_df_logx["Nf_cycles"])

fig, ax = plt.subplots()
plot_specimen_markers(ax, plot_df_logx, x_column="log10_Nf_cycles")
add_runout_arrows(ax, plot_df_logx, x_column="log10_Nf_cycles")
ax.set_yscale("log")
format_log10_x_ticks(ax)
finish_and_save(
    fig,
    ax,
    filename="AA7075_T651_SN_ylog_xlinear_log10labels",
    x_label=r"Cycles to failure, $N$",
)


# -----------------------------------------------------------------------------
# Figure 3: x-axis log only; y-axis linear
# -----------------------------------------------------------------------------
fig, ax = plt.subplots()
plot_specimen_markers(ax, plot_df, x_column="Nf_cycles")
add_runout_arrows(ax, plot_df, x_column="Nf_cycles")
ax.set_xscale("log")
finish_and_save(
    fig,
    ax,
    filename="AA7075_T651_SN_xlog_ylinear",
    x_label="Cycles to failure, N",
)
