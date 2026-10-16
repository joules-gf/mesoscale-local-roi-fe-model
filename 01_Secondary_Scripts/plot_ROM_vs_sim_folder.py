import os
import ntpath
import csv
import matplotlib.pyplot as plt
from matplotlib import rcParams


MATERIAL_REFERENCE_CURVES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    '00_Main_Scripts',
    'material_reference_curves'
)

REFERENCE_CURVES = {
    'AA7075-T651 cyclic ROM': 'aa7075-T651_monotonic_ROM_cyclic_parameters.csv',
    'AA2024-T351 cyclic ROM': 'aa2024-T351_monotonic_ROM_cyclic_parameters.csv',
    'AA7075-T6 cyclic ROM': 'aa7075-T6_monotonic_ROM_cyclic_parameters.csv',
    'AA7075-T651 cyclic experimental SvS': 'aa7075-T651_cyclic_experimental_SvS.csv',
    'AA7075-T651 cyclic experimental FvD': 'aa7075-T651_cyclic_experimental_FvD.csv',
}

REFERENCE_CURVE_PATHS = {
    ref_label: os.path.join(MATERIAL_REFERENCE_CURVES_DIR, file_name)
    for ref_label, file_name in REFERENCE_CURVES.items()
}


def resolve_reference_curve(reference_csv_or_label):
    """Return (reference_csv, ref_label) from either a reference label or CSV path."""
    if reference_csv_or_label in REFERENCE_CURVE_PATHS:
        return REFERENCE_CURVE_PATHS[reference_csv_or_label], reference_csv_or_label

    reference_csv = reference_csv_or_label
    reference_file = os.path.basename(os.path.normpath(reference_csv))
    reference_file = ntpath.basename(reference_file)

    for ref_label, file_name in REFERENCE_CURVES.items():
        if reference_file == file_name:
            return reference_csv, ref_label

    return reference_csv, os.path.splitext(reference_file)[0]


def load_csv(file_path, strain_col=0, stress_col=1):
    strain_vals, stress_vals = [], []
    with open(file_path, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            try:
                strain = float(row[strain_col])
                stress = float(row[stress_col])
                strain_vals.append(strain)
                stress_vals.append(stress)
            except (ValueError, IndexError):
                continue
    return strain_vals, stress_vals


def compute_area(x_vals, y_vals):
    area = 0.0
    for i in range(1, len(x_vals)):
        dx = x_vals[i] - x_vals[i - 1]
        avg_y = (y_vals[i] + y_vals[i - 1]) / 2
        area += dx * avg_y
    return area


def plot_folder_against_rom(
    reference_csv,
    results_folder,
    fig_title,
    show_area=False,
    show_plot=True,
    save_fig=True,

    # ---- Style parameters ----
    fig_size=(10, 6),
    label_size=14,
    title_size=16,
    legend_size=10,
    tick_size=12,
    reset_rc=True
):
    # ---- Optional: isolate rcParams changes ----
    if reset_rc:
        plt.rcdefaults()

    # ---- Apply rcParams ----
    rcParams['figure.figsize'] = fig_size
    rcParams['axes.labelsize'] = label_size
    rcParams['axes.titlesize'] = title_size
    rcParams['legend.fontsize'] = legend_size
    rcParams['xtick.labelsize'] = tick_size
    rcParams['ytick.labelsize'] = tick_size

    # Load reference
    reference_csv, ref_label = resolve_reference_curve(reference_csv)
    ref_strain, ref_stress = load_csv(reference_csv, strain_col=0, stress_col=1)

    if show_area:
        ref_area = compute_area(ref_strain, ref_stress)
        ref_label += f" (Area = {ref_area:.3f})"

# ---- Gather CSV files recursively ----
    csv_files = []

    for root, dirs, files in os.walk(results_folder):
        for file_name in files:
            if file_name.lower().endswith('.csv'):
                full_path = os.path.join(root, file_name)
                csv_files.append(full_path)

    if not csv_files:
        print("No simulation CSV files found in folder.")
        return

    fig, ax = plt.subplots()

    # Plot reference
    ax.plot(
        ref_strain,
        ref_stress,
        label=ref_label,
        linewidth=6,
        linestyle='--',
        c='k'
    )

    # Plot simulations
    for results_file in sorted(csv_files):
        strain, stress = load_csv(results_file, strain_col=1, stress_col=2)

        if not strain or not stress:
            print(f"Skipping invalid file: {results_file}")
            continue

        curve_name = os.path.splitext(os.path.basename(results_file))[0]

        if curve_name.startswith("_"):
            curve_name = curve_name.lstrip("_")

        label = curve_name

        if show_area:
            area = compute_area(strain, stress)
            label += f" (Area = {area:.3f})"

        ax.plot(strain, stress)#, label=label)

    ax.set_xlabel("Strain")
    ax.set_ylabel("Stress (MPa)")
    ax.set_title(fig_title)
    ax.grid(True)
    ax.legend()

    fig.tight_layout()

    if save_fig:
        save_path = os.path.join(results_folder, 'stress_strain_all_curves.png')
        fig.savefig(save_path, dpi=300)
        print(f"Figure saved to: {save_path}")

    if show_plot:
        plt.show()
    else:
        plt.close(fig)

if __name__ == '__main__':
  plot_folder_against_rom(
      reference_csv='AA7075-T651 cyclic ROM',
      results_folder=r"C:\Users\MAEadmin\Desktop\Github Repos\mesoscale-local-roi-fe-model\simulation_outputs\sensitivity-study\area-fraction",
      fig_title="Sensitivity to Random Variation of Area Fraction",
      fig_size=(19, 10),
      label_size=32,
      title_size=32,
      legend_size=32,
      tick_size=32
  )