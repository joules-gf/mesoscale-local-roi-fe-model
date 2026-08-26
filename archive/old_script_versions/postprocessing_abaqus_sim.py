import os
import csv
import numpy as np
import matplotlib.pyplot as plt

# Get Force vs Displacement from ODB
def extract_force_displacement(abaqus_output_directory, simulation_name):
    os.chdir(abaqus_output_directory)
    os.environ.update(
        {
            "ODB_FILE": simulation_name,
            "BOTTOMNODES": "BOTTOMNODES",
            "UPPERNODES": "UPPERNODES",
        }
    )
    os.system("abaqus cae noGUI=..\\..\\..\\00_Main_Scripts\\getForceDisp.py")

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
    return np.trapezoid(stress, strain)

def plot_simulation_against_rom(reference_csv, results_file, show_area=True, show_plot=True, save_fig=True):
    # Load AA7075-T6 reference (stress in col 0, strain in col 1)
    ref_strain, ref_stress = load_csv(reference_csv, strain_col=0, stress_col=1)
    ref_label = 'AA7075-T6 cyclic ROM'

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

    ax.plot(ref_strain, ref_stress, label=ref_label, linewidth=4, color='black')
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
            f'{curve_name}_stress_strain.png'))

def post_processing(abaqus_output_directory, simulation_name, stress_strain_plot_sttngs):
    # extract_force_displacement(abaqus_output_directory, simulation_name)
    reference_csv = os.path.join(
        os.path.dirname(__file__),
        'material_reference_curves',
        'aa7075-T6_cyclic_ROM.csv'
        )
    # results_file = os.path.join(os.path.dirname(abaqus_output_directory), f'{simulation_name}.csv')
    results_file = r'C:\Users\MAEadmin\OneDrive - Western Michigan University\01_Masters Class Docs\00_Research\01_Navy_Proposal\Grain Simulation Code\Ver7 - fully ChatGPT\generated_outputs\rRatio.4\rRatio.4.csv'
    
    if stress_strain_plot_sttngs is not None:
        show_area, show_plot, save_fig = stress_strain_plot_sttngs
        plot_simulation_against_rom(reference_csv, results_file, show_area, show_plot, save_fig)
    else:
        plot_simulation_against_rom(reference_csv, results_file) 


if __name__ == '__main__':
    # When running this file individually modify the input below

    abaqus_output_directory = r'C:\Users\MAEadmin\Desktop\mesoscale local ROI FE model\simulation_outputs\strainRratio.4\abaqus_files'
    simulation_name = 'strainRratio.4'

    # If stress_strain_plot_sttngs is None that means default post processing (show_area=True, show_plot=True, save_fig=True)
    stress_strain_plot_sttngs = None
    post_processing(abaqus_output_directory, simulation_name, stress_strain_plot_sttngs)