import os
import csv
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import xml.etree.ElementTree as ET
from wsl_windows_compat import run_abaqus_cae_no_gui
from material_reference import get_reference_material

# Get Force vs Displacement from ODB
def extract_force_displacement(abaqus_output_directory, simulation_name):
    os.environ.update(
        {
            "ODB_FILE": simulation_name,
            "BOTTOMNODES": "BOTTOMNODES",
            "UPPERNODES": "UPPERNODES",
        }
    )
    get_force_disp_script = os.path.join(os.path.dirname(__file__), "getForceDisp.py")
    run_abaqus_cae_no_gui(abaqus_output_directory, get_force_disp_script)

    # Check if the csv file was written
    csv_path = os.path.join(os.path.dirname(abaqus_output_directory), simulation_name + ".csv")
    if os.path.exists(csv_path):
        print(f"\n ✅ Post-processing completed. CSV saved to {csv_path}\n")
    else:
        print("⚠️ Post-processing failed or missing CSV.")

# Get values from CSV to plot against ROM
# WARNING: This framework assumes that the domain side length = 1, meaning cross sectional are = 1, meaning stress = force/1 and strain = displacement/1
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

def compute_area(strain, stress):
    trapezoid = getattr(np, "trapezoid", np.trapz)
    return trapezoid(stress, strain)

def plot_simulation_against_rom(
    reference_csv,
    results_file,
    show_area=True,
    show_plot=True,
    save_fig=True,
    ref_label='AA7075-T6 cyclic ROM'
):
    # Load reference ROM curve (stress in col 1, strain in col 0)
    ref_strain, ref_stress = load_csv(reference_csv, strain_col=0, stress_col=1)

    # Load and plot simulation CSV (strain in col 1, stress in col 2)
    strain, stress = load_csv(results_file, strain_col=1, stress_col=2)
    curve_name = os.path.splitext(os.path.basename(results_file))[0]

    if curve_name.startswith("_"):
        curve_name = curve_name.lstrip("_")

    label = curve_name

    if show_area:
        ref_area = compute_area(ref_strain, ref_stress)
        area = compute_area(strain, stress)
        ref_label += f" (Area = {ref_area:.3f})"
        label += f" (Area = {area:.3f})"

    fig, ax = plt.subplots()

    ax.plot(ref_strain, ref_stress, label=ref_label, linewidth=3, ls='--', color='black')
    ax.plot(strain, stress, label=label, color='red')
    ax.set_xlabel("Strain")
    ax.set_ylabel("Stress (MPa)")
    ax.set_title(f"Simulation '{curve_name}' Stress-Strain Comparison")
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    
    if show_plot:
        plt.show()
    if save_fig:
        fig.savefig(os.path.join(
            os.path.dirname(results_file),
            f'stress_strain_{curve_name}.png'))

def plot_cycles(results_file, simulation_name, save_fig=True):
    # Skip the first line (metadata), then read actual data
    df = pd.read_csv(results_file, skiprows=1)

    # Plot
    plt.figure()
    plt.plot(df["Step Time"], df["U_Y"], marker="o", linestyle="-")
    plt.xlabel("Step Time (s)")
    plt.ylabel("Displacement (mm)")
    plt.title(f"Simualtion '{simulation_name}' Displacement vs Step Time")
    plt.grid(True)
    plt.tight_layout()
    if save_fig:
        plt.savefig(os.path.join(os.path.dirname(results_file), f"cycles_{simulation_name}.png"))
    plt.show()

def plot_simulation_against_experimental(experimental_csv, results_file, show_plot=True, save_fig=True):
    # Load AA7075-T651 experimental reference (stress in col 1, strain in col 0)
    ref_strain, ref_stress = load_csv(experimental_csv, strain_col=0, stress_col=1)
    ref_label = f'AA7075-T651 1% strain experiment'

    # Load and plot simulation CSV (strain in col 1, stress in col 2)
    strain, stress = load_csv(results_file, strain_col=1, stress_col=2)
    curve_name = os.path.splitext(os.path.basename(results_file))[0]

    if curve_name.startswith("_"):
        curve_name = curve_name.lstrip("_")

    label = curve_name

    fig, ax = plt.subplots()

    ax.plot(ref_strain, ref_stress, label=ref_label, linewidth=2, ls='--', color='black')
    ax.plot(strain, stress, label=label, color='red')
    ax.set_xlabel("Strain")
    ax.set_ylabel("Stress (MPa)")
    ax.set_title(f"Simulation '{curve_name}' Cyclic Stress-Strain Comparison")
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    
    if show_plot:
        plt.show()
    if save_fig:
        fig.savefig(os.path.join(
            os.path.dirname(results_file),
            f'cyclic_stress_strain_{curve_name}.png'))

def get_reference_settings_from_resolved_input(abaqus_output_directory, simulation_name):
    simulation_folder = os.path.dirname(abaqus_output_directory)
    resolved_input = os.path.join(simulation_folder, f'{simulation_name}_resolved_input.xml')

    default_reference_csv = os.path.join(
        os.path.dirname(__file__),
        'material_reference_curves',
        'aa7075-T6_monotonic_ROM_cyclic_parameters.csv'
    )
    default_label = 'AA7075-T6 cyclic ROM'

    if not os.path.exists(resolved_input):
        return default_reference_csv, default_label

    try:
        root = ET.parse(resolved_input).getroot()
    except ET.ParseError:
        return default_reference_csv, default_label

    abaqus = root.find('abaqus')
    if abaqus is None:
        return default_reference_csv, default_label

    reference_csv = abaqus.findtext('reference_curve_csv')
    reference_label = abaqus.findtext('reference_plot_label')

    if reference_csv is None:
        reference_material = abaqus.findtext('reference_material')
        if reference_material is not None and reference_material.strip():
            ref = get_reference_material(reference_material)
            reference_csv = ref['reference_csv']
            reference_label = ref['plot_label']

    if reference_csv is None or not reference_csv.strip():
        reference_csv = default_reference_csv
    else:
        reference_csv = reference_csv.strip()

    if reference_label is None or not reference_label.strip():
        reference_label = default_label
    else:
        reference_label = reference_label.strip()

    return reference_csv, reference_label


def post_processing(abaqus_output_directory, simulation_name, stress_strain_plot_sttngs):
    extract_force_displacement(abaqus_output_directory, simulation_name)
    reference_csv, reference_label = get_reference_settings_from_resolved_input(
        abaqus_output_directory,
        simulation_name
    )
    results_file = os.path.join(os.path.dirname(abaqus_output_directory), f'{simulation_name}.csv')
    
    if stress_strain_plot_sttngs is not None:
        show_area, show_plot, save_fig = stress_strain_plot_sttngs
        plot_simulation_against_rom(reference_csv, results_file, show_area, show_plot, save_fig, reference_label)
    else:
        plot_simulation_against_rom(reference_csv, results_file, ref_label=reference_label)

    plot_cycles(results_file, simulation_name)

    experimental_csv = os.path.join(
        os.path.dirname(__file__),
        'material_reference_curves',
        'aa7075-T651_cyclic_experimental_SvS.csv'
        )
    plot_simulation_against_experimental(experimental_csv, results_file)

if __name__ == '__main__':
    # When running this file individually modify the input below

    abaqus_output_directory = r'C:\Users\MAEadmin\Desktop\microstructure fatigue simulation\simulation_outputs\baseline_parameters\abaqus_files'
    simulation_name = 'baseline_parameters'

    # If stress_strain_plot_sttngs is None that means default post processing (show_area=True, show_plot=True, save_fig=True)
    stress_strain_plot_sttngs = None
    post_processing(abaqus_output_directory, simulation_name, stress_strain_plot_sttngs)