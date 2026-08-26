# v00 - March 16th, 2026

## Warning #1: Change the simulation output directory below if running this file by itself
## Warning #2: If any of the phases DOES NOT contain the 'scale' (std deviation) key, ALL phases will get the 'scale' assigned as 20% of their 'loc' (mean) value.
## Warning #3: The code was built around handling multiple phases. In earlier development, I stumbled with an error while trying to run a single phase. Code structure changed but the error was never directly addressed.

# Importing necessary modules
import tkinter as tk
from tkinter import filedialog
import microstructpy as msp
import xml.etree.ElementTree as ET
from pathlib import Path
import tempfile
import os
import shutil

def select_input_file(initial_dir):
    """
    Opens a file selection dialog starting at the given directory.

    Parameters
    ----------
    initial_dir : str
        Path to the directory where the dialog should open.

    Returns
    -------
    str or None
        Full path of the selected file, or None if user cancels.
    """

    # Initialize root (hidden)
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Open file dialog
    file_path = filedialog.askopenfilename(
        initialdir=initial_dir,
        title="Select the XML input file"
    )

    # Destroy root after selection
    root.destroy()

    # Handle cancel case
    if not file_path:
        return None

    return file_path

def expand_all_includes(input_file):
    path = Path(input_file)
    root = ET.parse(path).getroot()
    _resolve_includes(root, path.parent)
    try:
        ET.indent(root, space="    ", level=0)
    except AttributeError:
        _indent_xml(root)

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False)
    ET.ElementTree(root).write(tmp.name)
    tmp.close()
    return tmp.name

def _resolve_includes(root, base_dir):
    for inc in list(root.findall('include')):
        inc_path = (base_dir / inc.text.strip()).resolve()
        inc_root = ET.parse(inc_path).getroot()

        # resolve includes inside the included file
        _resolve_includes(inc_root, inc_path.parent)

        # merge all top-level tags from the included file
        for inc_child in list(inc_root):
            if inc_child.tag == 'abaqus':
                base_abaqus = root.find('abaqus')
                if base_abaqus is None:
                    root.append(inc_child)
                else:
                    for child in list(inc_child):
                        base_abaqus.append(child)
                continue

            if inc_child.tag == 'material':
                root.append(inc_child)
                continue

            if inc_child.tag == 'domain':
                if root.find('domain') is None:
                    root.append(inc_child)
                continue

            if inc_child.tag == 'settings':
                base_settings = root.find('settings')
                if base_settings is None:
                    root.append(inc_child)
                else:
                    _merge_unique_children(base_settings, inc_child)
                continue

            # default: only add if missing
            if root.find(inc_child.tag) is None:
                root.append(inc_child)

        root.remove(inc)

def _merge_unique_children(target, source):
    existing_tags = {child.tag for child in list(target)}
    for child in list(source):
        if child.tag not in existing_tags:
            target.append(child)

def _indent_xml(elem, level=0, space="    "):
    indent = "\n" + (space * level)
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + space
        for child in elem:
            _indent_xml(child, level + 1, space)
            if not child.tail or not child.tail.strip():
                child.tail = indent + space
        if not elem[-1].tail or not elem[-1].tail.strip():
            elem[-1].tail = indent
    if not elem.tail or not elem.tail.strip():
        elem.tail = indent

def complete_input_data(input_file):

    # Start by ensuring all <include> tags are included/appended, even the one's not read by msp (ie. the <abaqus> tag)
    expanded = expand_all_includes(input_file)
    # Convert input data from XML file to a dictionary of strings. It will be later used to assign the size (from a scipy normal distribution), if it doesn't exist
    input_data_str = msp.cli.input2dict(expanded)

    # Same but not string dictionary
    input_data_to_run_1 = msp.cli.read_input(expanded)
    
    # Extract input data into different variables
    phases = input_data_str['input']['material']

    # Introducing the std deviation if not provided in the input file
    stds = [p['size'].get('scale', None) for p in phases]          # won't KeyError if missing

    if any(s is None for s in stds):
        means = [p['size']['loc'] for p in phases]

        for i, mean_value in enumerate(means):
            # Convert means from str to float
            means[i] = float(mean_value)

            # Incorporate the std deviation back into the phases list of dicts
            if stds[i] is None:
                stds[i] = means[i] * 0.2
                phases[i]['size']['scale'] = str(stds[i])
            else:        continue

            # Convert back to string
            means[i] = str(means[i])

    # Use all the extracted and modified input data to run the microstructpy CLI 
    input_data_to_run_2 = msp.cli.dict_convert(input_data_str)

    # 'domain' has to come from the non-string version of the input data. For some reason 'msp.cli.dict_convert' doesn't provide an neccesary attribute to the 'domain' dict
    domain = input_data_to_run_1['domain']
    phases = input_data_to_run_2['input']['material']

    # 'settings' can use any of the 'input_data_to_run' versions
    settings = input_data_to_run_2['input'].setdefault('settings', {})
    # Here this is trying to find settings dictionary within the input dictionary and if it doesn't exist it creates it

    # Function to change output directory 
    def change_mesh_output_directory(simulation_output_directory):

        # Copy simulation name
        simulation_name = os.path.splitext(os.path.basename(input_file))[0]
        # Use the simulation name to organize the output folder organization
        mesh_output_directory = os.path.join(simulation_output_directory, simulation_name, 'msp_mesh_files')
        
        # Add output directory to settings (msp creates the directory)
        settings['directory'] = mesh_output_directory

        return simulation_name, mesh_output_directory

    # Function to create the input and output folder even if they don't exist
    def create_directory_in_parent(new_folder_name: str) -> str:
        """
        Creates a directory in the parent of the given script directory.

        Parameters
        ----------
        script_dir : str
            Path to the current script directory
        new_folder_name : str
            Name of the folder to create in the parent directory

        Returns
        -------
        str
            Full path to the created (or existing) directory
        """
        
        script_path = Path(__file__).resolve()
        parent_path = script_path.parent.parent

        new_dir_path = parent_path / new_folder_name

        # Create directory (no error if it already exists)
        new_dir_path.mkdir(parents=True, exist_ok=True)

        return str(new_dir_path)

    # Create the simulation output directory if it doesn't exist
    simulation_output_directory_name = 'simulation_outputs'
    simulation_output_directory = create_directory_in_parent(simulation_output_directory_name)

    # Actually change the output directory
    simulation_name,  mesh_output_directory = change_mesh_output_directory(simulation_output_directory)

    # Ensure generation of .inp file from the simulation trimesh by requesting the abaqus -> tri -> filetypes -> settings
    filetypes = settings.setdefault('filetypes', {})
    filetypes['tri'] = 'abaqus'

    abaqus = input_data_to_run_2['input']['abaqus']
    complete_input = [domain, phases, settings, abaqus]

    return complete_input, simulation_name, simulation_output_directory, mesh_output_directory

def extract_plastic_stresses(abaqus_input_settings):
    plastic_stresses = []

    for plastic_stress in abaqus_input_settings['plastic_stresses']:
        plastic_stresses.append(plastic_stress)

    return plastic_stresses

# Function to insert data within a file (used for abaqus input file preparation)
def insert_text_in_abaqus_file(
    mesh_file,
    text_to_insert,
    search_string=None,
    insert_below=True,
    mode="search"
):
    """
    Insert text into an Abaqus input file.

    Parameters
    ----------
    mesh_file : str
        Path to the file.

    text_to_insert : str
        Text that will be inserted.

    search_string : str | None
        String to search for when mode="search".

    insert_below : bool
        If True insert below the matched line, otherwise above.

    mode : str
        "search" -> insert relative to search_string
        "append" -> append text at the end of the file
    """

    with open(mesh_file, "r") as file:
        lines = file.readlines()

    # ------------------------------------------------
    # APPEND MODE
    # ------------------------------------------------
    if mode == "append":

        # Ensure newline before appending
        if lines and not lines[-1].endswith("\n"):
            lines[-1] = lines[-1] + "\n"

        lines.append(text_to_insert + "\n")

        with open(mesh_file, "w") as file:
            file.writelines(lines)

        return

    # ------------------------------------------------
    # SEARCH MODE
    # ------------------------------------------------
    if search_string is None:
        raise ValueError("search_string must be provided when mode='search'")

    new_lines = []
    text_inserted = False

    for line in lines:
        stripped_line = line.strip()

        # Insert ABOVE
        if stripped_line == search_string and not insert_below and not text_inserted:
            new_lines.append(text_to_insert + "\n")
            text_inserted = True

        new_lines.append(line)

        # Insert BELOW
        if stripped_line == search_string and insert_below and not text_inserted:
            new_lines.append(text_to_insert + "\n")
            text_inserted = True

    if not text_inserted:
        raise ValueError(f"'{search_string}' was not found in the file.")

    with open(mesh_file, "w") as file:
        file.writelines(new_lines)


# Actually modifying the abaqus input file
def abaqus_input_file_completion(mesh_file, abaqus, phases, plastic_stresses):

    # Keeping the simulation .dat and .msg file concise
    mod_dat_msg_file_content = """*Preprint, echo=NO, model=NO, history=NO, contact=NO"""

    insert_text_in_abaqus_file(
        mesh_file=mesh_file,
        search_string="** Generated by: MicroStructPy",
        text_to_insert=mod_dat_msg_file_content,
        insert_below=True
    )

    # Writing sections
    section_lines = []
    for phase_number, _ in enumerate(phases):
        section_lines.append(f"** Section: Section_Material{phase_number}")
        section_lines.append(
            f"*Solid Section, elset = Set-E-Material-{phase_number}, material = Material-{phase_number}"
        )
        section_lines.append(",")
    section_input = "\n".join(section_lines)

    insert_text_in_abaqus_file(
        mesh_file=mesh_file,
        search_string="*End Part",
        text_to_insert=section_input,
        insert_below=False
    )

    # Function to extract the boundary nodes
    def extract_boundary_nodes(filename, surface_name):
        with open(filename, "r") as file:
            lines = file.readlines()

        boundary_nodes = set()

        # Find all secondary surface names
        secondary_surfaces = []
        capture = False
        for i, line in enumerate(lines):
            if f"*Surface, name={surface_name}, combine=union" in line:
                capture = True
                continue
            if capture:
                if line.strip().startswith("*"):  # Stop if we reach another section
                    break
                secondary_surfaces.append(line.strip())

        if not secondary_surfaces:
            print(f"Surface name {surface_name} not found in the file.")
            return boundary_nodes

        for secondary_surface in secondary_surfaces:
            # Find the element numbers and facet types from secondary surface
            element_facet_pairs = []
            for i, line in enumerate(lines):
                if f"*Surface, name={secondary_surface}, type=element" in line:
                    j = i + 1
                    while j < len(lines) and not lines[j].strip().startswith("*"):
                        parts = lines[j].strip().split(",")
                        if len(parts) >= 2:
                            try:
                                element_facet_pairs.append(
                                    (int(parts[0]), parts[1].strip())
                                )
                            except ValueError:
                                print(f"Invalid element number in line: {lines[j]}")
                        j += 1
                    break

            if not element_facet_pairs:
                print(f"Secondary surface definition not found for {secondary_surface}.")
                continue

            # Find *Element section and extract node numbers for each element
            elements_nodes = {}
            element_section_found = False
            for line in lines:
                if "*Element" in line:
                    element_section_found = True
                    continue
                elif element_section_found:
                    if line.strip().startswith("*"):  # Stop if we reach another dataset
                        break
                    parts = line.strip().split(",")
                    try:
                        element_id = int(parts[0])
                        node_list = [int(n) for n in parts[1:4]]
                        elements_nodes[element_id] = node_list
                    except ValueError:
                        print(f"Invalid node data in line: {line}")

            # Determine the nodes based on facet type
            facet_map = {"S1": [0, 1], "S2": [1, 2], "S3": [2, 0]}

            for element_number, facet_type in element_facet_pairs:
                if element_number not in elements_nodes:
                    print(f"Element number {element_number} not found in *Element section.")
                    continue

                if facet_type not in facet_map:
                    print(
                        f"Invalid facet type {facet_type} found for element {element_number}."
                    )
                    continue

                selected_nodes = [
                    elements_nodes[element_number][i] for i in facet_map[facet_type]
                ]
                boundary_nodes.update(selected_nodes)

        return boundary_nodes
    
    # Read boundary nodes to assign boundary conditions.
    upper_surface_nodes = extract_boundary_nodes(mesh_file, "Ext-Surface-4")
    bottom_surface_nodes = extract_boundary_nodes(mesh_file, "Ext-Surface-3")

    def build_node_set_string(nodeset_name, node_collection):
        # Allow either a single node (int) or a collection of nodes
        if isinstance(node_collection, int):
            node_list = [node_collection]
        else:
            node_list = list(node_collection)  # convert to list for slicing

        nset_input = ""
        nset_input += f"*Nset, nset={nodeset_name}\n"

        for i in range(0, len(node_list), 16):
            line = ",".join(str(node) for node in node_list[i:i + 16])
            nset_input += line + "\n"

        return nset_input

    upper_surface_nodes = build_node_set_string("UpperNodes", upper_surface_nodes)
    bottom_surface_nodes = build_node_set_string("BottomNodes", bottom_surface_nodes)

    def find_middle_bottom_node(mesh_file):
        """
        Finds the first node at y = -0.5 whose x coordinate starts with 0.0
        """

        with open(mesh_file, "r") as file:
            in_node_block = False

            for line in file:
                line = line.strip()

                if line.startswith("*Node"):
                    in_node_block = True
                    continue

                if line.startswith("*") and in_node_block:
                    # Exit node block
                    break

                if not in_node_block or not line or line.startswith("**"):
                    continue

                node_id, x, y = line.split(",")[:3]

                if y.strip() == "-0.5" and x.strip().startswith("0.0"):
                    return int(node_id)

        return None

    middle_bottom_node = find_middle_bottom_node(mesh_file)
    middle_bottom_node = build_node_set_string("MidBottomNode", middle_bottom_node)

    insert_text_in_abaqus_file(
        mesh_file=mesh_file,
        search_string="*End Part",
        text_to_insert=upper_surface_nodes + bottom_surface_nodes + middle_bottom_node,
        insert_below=False
    )

    # Checking if it'll be a cyclic or monotonic step
    cyclic_parameters = abaqus.get('cyclic_parameters', None)

    # If it is a cyclic simulation:
    if cyclic_parameters is not None:
        rRatio_strain = cyclic_parameters['rRatio_strain']
        frequency_hz = cyclic_parameters['frequency_hz']
        start_min = cyclic_parameters['start_min']

        def write_periodic_amplitude(
            rRatio_strain,
            frequency_hz,
            start_min=True
        ):
            import math

            amp_max = 1.0
            amp_min = rRatio_strain * amp_max
            A0 = (amp_max + amp_min) / 2
            B = (amp_max - amp_min) / 2
            if start_min:
                phi = - math.pi/2
            else:
                phi = 0
            
            omega = 2 * math.pi * frequency_hz

            amplitude_lines = [
                "*Amplitude, name=Amp-1, definition=Periodic",
                f"1, {omega:.4f}, {phi:.4f}, {A0}",
                f"0.0, {B}",
            ]
            amplitude_spec = "\n".join(amplitude_lines)

            insert_text_in_abaqus_file(
                mesh_file=mesh_file,
                search_string="*End Assembly",
                text_to_insert=amplitude_spec,
                insert_below=True
            )
        write_periodic_amplitude(
            rRatio_strain,
            frequency_hz,
            start_min
            )

        # Use the time increment to define the step time increment, the number of output frames, and the minimum increment
        time_increment_s = cyclic_parameters['time_increment_s']
        output_frames = 1/time_increment_s
        min_increment = time_increment_s * 0.1
    else:
        output_frames = 100
        


    def write_materials_properties():
        material_lines = ["**", "**MATERIALS**"]
        E_MPa = abaqus['E']
        nu = abaqus['nu']
        for phase_number, plastic_stress in enumerate(plastic_stresses):
            material_lines.extend([
                f"*Material, name=Material-{phase_number}",
                "*Elastic",
                f"{E_MPa}, {nu}",
                "*Plastic",
                f"{plastic_stress}, 0.0",
                f"{plastic_stress}, 1.0",
            ])
        materials_spec = "\n".join(material_lines)

        insert_text_in_abaqus_file(
            mesh_file=mesh_file,
            text_to_insert=materials_spec,
            mode="append"
            )

    write_materials_properties()

    def write_fixed_boundary_conditions():
        instance_name = "I-Part-1"

        def inst_set(set_name):
            return f"{instance_name}.{set_name}"

        bc_lines = ["**BOUNDARY_CONDITIONS**"]
        boundary_blocks = [
            (
                "** Name: Bottom_Side Type: Displacement / Rotation",
                [
                    f"{inst_set('BottomNodes')}, 2, 2",
                    f"{inst_set('BottomNodes')}, 6, 6",
                ],
            ),
            (
                "** Name: MidBottomNode Type: Displacement / Rotation",
                [
                    f"{inst_set('MidBottomNode')}, 1, 1",
                ],
            ),
        ]

        for boundary_name, boundary_values in boundary_blocks:
            bc_lines.append(boundary_name)
            bc_lines.append("*Boundary")
            for boundary_value in boundary_values:
                bc_lines.append(boundary_value)

        bc_lines.append("** ----------------------------------------------------------------")
        bc_spec = "\n".join(bc_lines)

        insert_text_in_abaqus_file(
            mesh_file=mesh_file,
            text_to_insert=bc_spec,
            mode="append"
        )

    write_fixed_boundary_conditions()

    def write_step_definition():
        increment_number = abaqus.setdefault('num_increments_step', 100)

        step_lines = [
            "**",
            "** STEP: Step - 1",
            "**",
            f"*Step, name = Step - 1, nlgeom = NO, inc={increment_number}",
            "*Static",
            "** Numbers in the line below represent respectively: initial increment, total time, minimum increment, maximum increment",
        ]

        if cyclic_parameters is not None:
            step_lines.append(f"{time_increment_s:.3f}, 1.0, {min_increment:.4f}, {time_increment_s:.3f}")
        else:
            step_lines.append("1., 1., 1e-5, 1.")

        step_spec = "\n".join(step_lines)

        insert_text_in_abaqus_file(
            mesh_file=mesh_file,
            text_to_insert=step_spec,
            mode="append"
        )
    write_step_definition()

    def write_displacement_boundary_condition():
        displacement_yy = abaqus['displacement_yy']
        instance_name = "I-Part-1"

        def inst_set(set_name):
            return f"{instance_name}.{set_name}"

        disp_bc_lines = [
            "** BOUNDARY CONDITIONS **",
            "** Name: upperDisp Type: Displacement / Rotation ",
        ]

        if cyclic_parameters is not None:
            disp_bc_lines.append("*Boundary, amplitude=Amp-1")
        else:
            disp_bc_lines.append("*Boundary")

        disp_bc_lines.append(f"{inst_set('UpperNodes')}, 2, 2, {displacement_yy:.3f}")
        disp_bc_spec = "\n".join(disp_bc_lines)

        insert_text_in_abaqus_file(
            mesh_file=mesh_file,
            text_to_insert=disp_bc_spec,
            mode="append"
        )

    write_displacement_boundary_condition()

    def write_output_requests():
        output_lines = [
            "**",
            "** OUTPUT REQUESTS **",
            "*Restart, write, frequency=0",
            "**",
            "** FIELD OUTPUT: F-Output-1",
            "**",
            f"*Output, Field, Number intervals = {int(output_frames)}",
            "*Node Output",
            "CF, RF, U",
            "*Element Output, directions=YES",
            "E, MISES, PE, S, PEEQ",
            "**",
            "** HISTORY OUTPUT: H-Output-1",
            "**",
            "*Output, history, variable=PRESELECT",
            "*End Step",
        ]
        output_spec = "\n".join(output_lines)

        insert_text_in_abaqus_file(
            mesh_file=mesh_file,
            text_to_insert=output_spec,
            mode="append"
        )
    write_output_requests()



def generate_input(input_files_folder):
    # If 'input_files_folder' is empty it automatically opens in the location of this script
    if not input_files_folder.strip():
        input_files_folder = Path(__file__).resolve()

    # Start by selecting the input file
    input_file_path = select_input_file(input_files_folder)

    # The information provided in the input file (currently) isn't enough to run the simulation, so we fill the gaps
    complete_input, simulation_name, simulation_output_directory, mesh_output_directory = complete_input_data(input_file_path)

    # Separate input to run microstructpy
    domain, phases, settings, abaqus = complete_input

    # Run the microstructpy CLI with the extracted input data
    if True:
        msp.cli.run(phases=phases, domain=domain, **settings)

    plastic_stresses = extract_plastic_stresses(abaqus)
    
    # Create a place to hold the Abaqus input file and simulation files
    abaqus_output_directory = os.path.join(simulation_output_directory, simulation_name, 'abaqus_files')
    os.makedirs(abaqus_output_directory, exist_ok=True)

    # Copy the Abaqus input file from mesh_output_directory
    for filename in os.listdir(mesh_output_directory):
        if filename.endswith('.inp'):
            copied_file_path = os.path.join(mesh_output_directory, filename)
            pasted_file_name = f"{simulation_name}.inp"
            pasted_file_path = os.path.join(abaqus_output_directory, pasted_file_name)

            # Perform the copy action
            shutil.copy2(copied_file_path, pasted_file_path)
            break
        else:
            continue
    
    # Fill in the missing parameters so that Abaqus can run the simulation
    abaqus_input_file_completion(pasted_file_path, abaqus, phases, plastic_stresses)

    return abaqus_output_directory, simulation_name, simulation_output_directory


## MODIFY THIS LINE OF CODE:
### Options: 1) Empty string, 2) a raw string (ie. "r'text'") with the path to your inputs folder
#### input_files_folder = ''
#### input_files_folder = r'C:\Users\MAEadmin\Desktop\mesoscale local ROI FE model\simulation_inputs'

input_files_folder = r'C:\Users\MAEadmin\Desktop\mesoscale local ROI FE model\simulation_inputs'


if __name__ == '__main__':

    generate_input(input_files_folder)