"""Plot sliding-pair-averaged phase mean diameter versus stress at 1% strain.

This reads the original same-mean-diameter sensitivity-study cases from
``reference_outputs/Sensitivity Study/lower-bound-diameter-equal-4all-phases`` and
averages adjacent sliding pairs: (01,02), (02,03), ..., (19,20).
Rerun/validation points are intentionally not included.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from plot_phase_mean_diameter_vs_stress_1pct import (
    FIG_SIZE,
    LABEL_SIZE,
    LEGEND_SIZE,
    RESULTS_DIR,
    TICK_SIZE,
    TITLE_SIZE,
    collect_data,
)


OUTPUT_FIG = RESULTS_DIR / "phase_mean_diameter_vs_stress_at_1pct_strain_sliding_pair_averaged.png"
OUTPUT_CSV = RESULTS_DIR / "phase_mean_diameter_vs_stress_at_1pct_strain_sliding_pair_averaged.csv"


def case_number(case_name: str) -> int:
    """Extract the integer case number from names like bp_same_size_case_08."""
    return int(case_name.rsplit("_", maxsplit=1)[-1])


def sliding_pair_average_rows(rows: list[tuple[float, float, str]]) -> list[tuple[float, float, str]]:
    """Average adjacent sliding case pairs: 01+02, 02+03, ..., 19+20."""
    by_case = {case_number(case_name): (diameter, stress, case_name) for diameter, stress, case_name in rows}
    averaged: list[tuple[float, float, str]] = []

    for first_case in range(1, 20):
        second_case = first_case + 1
        if first_case not in by_case or second_case not in by_case:
            print(f"Skipping pair {first_case:02d}-{second_case:02d}: missing case")
            continue

        first_diameter, first_stress, first_name = by_case[first_case]
        second_diameter, second_stress, second_name = by_case[second_case]
        avg_diameter = (first_diameter + second_diameter) / 2.0
        avg_stress = (first_stress + second_stress) / 2.0
        averaged.append((avg_diameter, avg_stress, f"{first_name}+{second_name}"))

    return averaged


def write_csv(rows: list[tuple[float, float, str]], output_csv: Path = OUTPUT_CSV) -> Path:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        f.write("pair,mean_diameter_microns_avg,stress_at_1pct_MPa_avg\n")
        for diameter, stress, pair_name in rows:
            f.write(f"{pair_name},{diameter:.12g},{stress:.12g}\n")
    return output_csv


def make_plot(rows: list[tuple[float, float, str]], output_fig: Path = OUTPUT_FIG) -> Path:
    diameters = [row[0] for row in rows]
    stresses = [row[1] for row in rows]

    fig, ax = plt.subplots(figsize=FIG_SIZE)
    ax.plot(
        diameters,
        stresses,
        marker="o",
        linewidth=2,
        markersize=7,
        label="Sliding pair averages",
    )

    ax.set_xlabel("Phase mean diameter (microns)", fontsize=LABEL_SIZE)
    ax.set_ylabel("Stress at 1% strain (MPa)", fontsize=LABEL_SIZE)
    ax.set_title(
        "Sliding-Pair-Averaged Phase Mean Diameter vs Stress at 1% Strain",
        fontsize=TITLE_SIZE,
    )
    ax.tick_params(axis="both", labelsize=TICK_SIZE)
    ax.grid(True, alpha=0.35)
    ax.legend(fontsize=LEGEND_SIZE)

    fig.tight_layout()
    output_fig.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_fig, dpi=300)
    plt.close(fig)
    return output_fig


def main() -> None:
    original_rows = collect_data()
    averaged_rows = sliding_pair_average_rows(original_rows)
    output_csv = write_csv(averaged_rows)
    output_fig = make_plot(averaged_rows)

    print(f"Saved CSV: {output_csv}")
    print(f"Saved figure: {output_fig}")
    print("Sliding-pair-averaged data points:")
    for diameter, stress, pair_name in averaged_rows:
        print(f"  {pair_name}: diameter={diameter:g} microns, stress={stress:.6g} MPa")


if __name__ == "__main__":
    main()
