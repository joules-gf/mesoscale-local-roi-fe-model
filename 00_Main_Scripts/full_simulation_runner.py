import argparse
from pathlib import Path

from abaqus_input_generation_v02 import generate_input
from run_abaqus_sim import run_simulation
from postprocessing_abaqus_sim_v01 import post_processing
from wsl_windows_compat import AbaqusUnavailableError, is_wsl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_FOLDER = PROJECT_ROOT / "simulation_inputs" / "AL7075-T6"


def run_full_simulation(
    input_files_folder=None,
    input_file=None,
    run_abaqus=True,
    run_postprocessing=True,
):
    """Run the research workflow with CLI-friendly path defaults.

    In WSL, MicroStructPy input generation can run locally, but Abaqus usually
    lives on Windows.  If Abaqus cannot be reached, the pipeline leaves the
    generated `.inp` file in `simulation_outputs/<case>/abaqus_files/` so it can
    be submitted from Windows manually or after configuring the bridge.
    """
    if input_files_folder is None:
        input_files_folder = DEFAULT_INPUT_FOLDER

    abaqus_output_directory, simulation_name = generate_input(
        str(input_files_folder),
        input_file=str(input_file) if input_file else None,
    )

    if run_abaqus:
        try:
            run_simulation(abaqus_output_directory, simulation_name)
        except AbaqusUnavailableError as exc:
            print("\n⚠️ Abaqus is not available from this environment.")
            print(exc)
            print("Generated Abaqus input files are ready here:")
            print(f"  {abaqus_output_directory}\n")
            if is_wsl():
                print("WSL note: install/use Abaqus on Windows, expose it through cmd.exe, ")
                print("or copy/run the generated .inp from the Windows Abaqus shell.")
            return abaqus_output_directory, simulation_name

    if run_postprocessing:
        stress_strain_plot_sttngs = None
        post_processing(abaqus_output_directory, simulation_name, stress_strain_plot_sttngs)

    return abaqus_output_directory, simulation_name


def parse_args():
    parser = argparse.ArgumentParser(description="Run the mesoscale local ROI FE model workflow.")
    parser.add_argument(
        "--input-folder",
        default=str(DEFAULT_INPUT_FOLDER),
        help="Folder containing XML input files. Defaults to simulation_inputs/AL7075-T6.",
    )
    parser.add_argument(
        "--input-file",
        help="Specific XML file to run. If omitted, a file picker is used unless --input-folder is enough for your workflow.",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Generate MicroStructPy/Abaqus input files but do not launch Abaqus or postprocessing.",
    )
    parser.add_argument(
        "--skip-postprocessing",
        action="store_true",
        help="Run Abaqus but skip ODB postprocessing/plotting.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        run_full_simulation(
            input_files_folder=args.input_folder,
            input_file=args.input_file,
            run_abaqus=not args.generate_only,
            run_postprocessing=not args.skip_postprocessing and not args.generate_only,
        )
    except RuntimeError as exc:
        print(f"\n❌ {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
