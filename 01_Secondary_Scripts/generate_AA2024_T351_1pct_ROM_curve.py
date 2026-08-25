import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---------------------------------
# AA2024-T351 Ramberg-Osgood curve
# Values copied from curvature_ofROM.py materials dictionary:
#   'AA2024-T351': [731e2, 662, 0.070, 449]
# Interpreted as [E_MPa, H_prime_MPa, n_prime, stress_max_MPa]
# ---------------------------------
MATERIAL_NAME = "AA2024-T351"
E_MPa = 731e2
H_prime_MPa = 662
n_prime = 0.070
TARGET_STRAIN = 0.010
N_POINTS = 1001

SCRIPT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REFERENCE_CURVE_DIR = os.path.join(REPO_ROOT, "00_Main_Scripts", "material_reference_curves")
OUTPUT_PLOT_DIR = os.path.join(SCRIPT_DIR, "rom_outputs")

CSV_PATH = os.path.join(
    REFERENCE_CURVE_DIR,
    "aa2024-T351_monotonic_ROM_1pct_strain.csv",
)
PNG_PATH = os.path.join(
    OUTPUT_PLOT_DIR,
    "AA2024-T351_ramberg_osgood_curve_to_1pct_strain.png",
)


def ramberg_osgood_strain(stress_MPa):
    return (stress_MPa / E_MPa) + (stress_MPa / H_prime_MPa) ** (1 / n_prime)


def find_stress_for_target_strain(target_strain):
    # Bisection, because strain(stress) is monotonic for positive stress.
    low = 0.0
    high = max(449.0, E_MPa * target_strain)

    while ramberg_osgood_strain(high) < target_strain:
        high *= 1.5

    for _ in range(100):
        mid = 0.5 * (low + high)
        if ramberg_osgood_strain(mid) < target_strain:
            low = mid
        else:
            high = mid

    return 0.5 * (low + high)


def main():
    os.makedirs(REFERENCE_CURVE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_PLOT_DIR, exist_ok=True)

    stress_at_1pct = find_stress_for_target_strain(TARGET_STRAIN)
    strain = np.linspace(0.0, TARGET_STRAIN, N_POINTS)

    # Invert the Ramberg-Osgood relation for a strain-spaced CSV/plot.
    stress = np.zeros_like(strain)
    for i, strain_value in enumerate(strain):
        if strain_value == 0:
            stress[i] = 0.0
        else:
            stress[i] = find_stress_for_target_strain(strain_value)

    elastic_strain = stress / E_MPa
    plastic_strain = strain - elastic_strain

    df = pd.DataFrame({
        "strain": strain,
        "stress_MPa": stress,
        "elastic_strain": elastic_strain,
        "plastic_strain": plastic_strain,
    })
    df.to_csv(CSV_PATH, index=False)

    calibri_path = "/mnt/c/Windows/Fonts/calibri.ttf"
    if os.path.exists(calibri_path):
        font_manager.fontManager.addfont(calibri_path)
        font_family = "Calibri"
    else:
        font_family = "DejaVu Sans"

    plt.rcParams.update({
        "figure.figsize": (8, 6),
        "font.family": font_family,
        "axes.titlesize": 22,
        "axes.labelsize": 20,
        "xtick.labelsize": 16,
        "ytick.labelsize": 16,
        "legend.fontsize": 16,
        "lines.linewidth": 3,
        "axes.grid": True,
    })

    fig, ax = plt.subplots()
    ax.plot(strain, stress, color="#1f77b4", label="Ramberg-Osgood")
    ax.scatter([TARGET_STRAIN], [stress_at_1pct], color="#d62728", zorder=3, label=f"1% strain: {stress_at_1pct:.1f} MPa")
    ax.set_title(f"{MATERIAL_NAME} Stress-Strain Curve")
    ax.set_xlabel("Strain")
    ax.set_ylabel("Stress (MPa)")
    ax.set_xlim(0, TARGET_STRAIN * 1.02)
    ax.set_ylim(0, max(stress) * 1.08)
    ax.legend(loc="lower right")
    ax.grid(True, color="#b0b0b0", alpha=0.7)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Material: {MATERIAL_NAME}")
    print(f"E = {E_MPa:.1f} MPa ({E_MPa/1000:.1f} GPa)")
    print(f"H' = {H_prime_MPa:.1f} MPa")
    print(f"n' = {n_prime:.3f}")
    print(f"Stress at 1% strain = {stress_at_1pct:.6f} MPa")
    print(f"CSV: {CSV_PATH}")
    print(f"PNG: {PNG_PATH}")


if __name__ == "__main__":
    main()
