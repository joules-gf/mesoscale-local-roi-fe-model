import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---------------------------------
# General Ramberg-Osgood curve generator
# ---------------------------------
# Material values follow the same convention used in curvature_ofROM.py:
#   [E_MPa, H_prime_MPa, n_prime, stress_max_MPa]
#
# The default is AA2024-T351 up to 1% strain because that is the reference
# curve currently used for the AA2024-T351 comparison simulations.
# ---------------------------------
MATERIALS = {
    "AA7075-T6": [71e3, 977, 0.106, 521],
    "AA2024-T351": [731e2, 662, 0.070, 449],
    "AA7075-T651": [70e3, 852, 0.074, 543],
}

DEFAULT_MATERIAL_NAME = "AA2024-T351"
DEFAULT_TARGET_STRAIN = 0.010
DEFAULT_N_POINTS = 1001

SCRIPT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
REFERENCE_CURVE_DIR = os.path.join(REPO_ROOT, "00_Main_Scripts", "material_reference_curves")
OUTPUT_PLOT_DIR = os.path.join(SCRIPT_DIR, "rom_outputs")


def clean_material_name(material_name):
    return material_name.replace("/", "_").replace(" ", "_")


def strain_label(target_strain):
    # 0.010 -> 1pct, 0.015 -> 1p5pct, 0.0025 -> 0p25pct
    percent_value = target_strain * 100
    text = f"{percent_value:g}".replace(".", "p")
    return f"{text}pct"


def get_default_paths(material_name, target_strain):
    clean_name = clean_material_name(material_name)
    label = strain_label(target_strain)

    csv_path = os.path.join(
        REFERENCE_CURVE_DIR,
        f"{clean_name}_monotonic_ROM_{label}_strain.csv",
    )
    png_path = os.path.join(
        OUTPUT_PLOT_DIR,
        f"{material_name}_ramberg_osgood_curve_to_{label}_strain.png",
    )

    # Preserve the already-used AA2024 1% filenames so existing comparison
    # scripts and documentation do not break just because the generator became general.
    if material_name == "AA2024-T351" and abs(target_strain - 0.010) < 1e-12:
        csv_path = os.path.join(
            REFERENCE_CURVE_DIR,
            "aa2024-T351_monotonic_ROM_1pct_strain.csv",
        )
        png_path = os.path.join(
            OUTPUT_PLOT_DIR,
            "AA2024-T351_ramberg_osgood_curve_to_1pct_strain.png",
        )

    return csv_path, png_path


def ramberg_osgood_strain(stress_MPa, E_MPa, H_prime_MPa, n_prime):
    return (stress_MPa / E_MPa) + (stress_MPa / H_prime_MPa) ** (1 / n_prime)


def find_stress_for_target_strain(target_strain, E_MPa, H_prime_MPa, n_prime, stress_max_MPa):
    # Bisection, because strain(stress) is monotonic for positive stress.
    low = 0.0
    high = max(float(stress_max_MPa), E_MPa * target_strain)

    while ramberg_osgood_strain(high, E_MPa, H_prime_MPa, n_prime) < target_strain:
        high *= 1.5

    for _ in range(100):
        mid = 0.5 * (low + high)
        if ramberg_osgood_strain(mid, E_MPa, H_prime_MPa, n_prime) < target_strain:
            low = mid
        else:
            high = mid

    return 0.5 * (low + high)


def generate_rom_curve(material_name, target_strain, n_points, csv_path, png_path):
    if material_name not in MATERIALS:
        available = ", ".join(MATERIALS)
        raise ValueError(f"Unknown material '{material_name}'. Available materials: {available}")

    E_MPa, H_prime_MPa, n_prime, stress_max_MPa = MATERIALS[material_name]

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)

    stress_at_target = find_stress_for_target_strain(
        target_strain,
        E_MPa,
        H_prime_MPa,
        n_prime,
        stress_max_MPa,
    )
    strain = np.linspace(0.0, target_strain, n_points)

    # Invert the Ramberg-Osgood relation for a strain-spaced CSV/plot.
    stress = np.zeros_like(strain)
    for i, strain_value in enumerate(strain):
        if strain_value == 0:
            stress[i] = 0.0
        else:
            stress[i] = find_stress_for_target_strain(
                strain_value,
                E_MPa,
                H_prime_MPa,
                n_prime,
                stress_max_MPa,
            )

    elastic_strain = stress / E_MPa
    plastic_strain = strain - elastic_strain

    df = pd.DataFrame({
        "strain": strain,
        "stress_MPa": stress,
        "elastic_strain": elastic_strain,
        "plastic_strain": plastic_strain,
    })
    df.to_csv(csv_path, index=False)

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

    target_percent = target_strain * 100

    fig, ax = plt.subplots()
    ax.plot(strain, stress, color="#1f77b4", label="Ramberg-Osgood")
    ax.scatter(
        [target_strain],
        [stress_at_target],
        color="#d62728",
        zorder=3,
        label=f"{target_percent:g}% strain: {stress_at_target:.1f} MPa",
    )
    ax.set_title(f"{material_name} Stress-Strain Curve")
    ax.set_xlabel("Strain")
    ax.set_ylabel("Stress (MPa)")
    ax.set_xlim(0, target_strain * 1.02)
    ax.set_ylim(0, max(stress) * 1.08)
    ax.legend(loc="lower right")
    ax.grid(True, color="#b0b0b0", alpha=0.7)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Material: {material_name}")
    print(f"E = {E_MPa:.1f} MPa ({E_MPa/1000:.1f} GPa)")
    print(f"H' = {H_prime_MPa:.1f} MPa")
    print(f"n' = {n_prime:.3f}")
    print(f"Stress at {target_percent:g}% strain = {stress_at_target:.6f} MPa")
    print(f"CSV: {csv_path}")
    print(f"PNG: {png_path}")

    return csv_path, png_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Ramberg-Osgood stress-strain curve from stored material parameters."
    )
    parser.add_argument(
        "--material",
        default=DEFAULT_MATERIAL_NAME,
        choices=sorted(MATERIALS),
        help="Material entry to use from the local MATERIALS dictionary.",
    )
    parser.add_argument(
        "--target-strain",
        type=float,
        default=DEFAULT_TARGET_STRAIN,
        help="Final total strain for the generated curve, e.g. 0.010 for 1%% strain.",
    )
    parser.add_argument(
        "--n-points",
        type=int,
        default=DEFAULT_N_POINTS,
        help="Number of strain-spaced points to write to the CSV.",
    )
    parser.add_argument(
        "--csv-path",
        default=None,
        help="Optional custom CSV output path. Defaults to 00_Main_Scripts/material_reference_curves/.",
    )
    parser.add_argument(
        "--png-path",
        default=None,
        help="Optional custom PNG output path. Defaults to 01_Secondary_Scripts/rom_outputs/.",
    )
    args = parser.parse_args()

    if args.target_strain <= 0:
        raise ValueError("target-strain must be positive")
    if args.n_points < 2:
        raise ValueError("n-points must be at least 2")

    default_csv_path, default_png_path = get_default_paths(args.material, args.target_strain)
    csv_path = args.csv_path or default_csv_path
    png_path = args.png_path or default_png_path

    generate_rom_curve(
        material_name=args.material,
        target_strain=args.target_strain,
        n_points=args.n_points,
        csv_path=csv_path,
        png_path=png_path,
    )


if __name__ == "__main__":
    main()
