from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
REFERENCE_CURVE_DIR = SCRIPT_DIR / "material_reference_curves"

# ---------------------------------
# Ramberg-Osgood reference materials
# Values are interpreted as:
#   [E_MPa, H_prime_MPa, n_prime, stress_max_MPa]
# ---------------------------------
REFERENCE_MATERIALS = {
    "AA7075-T6": {
        "name": "AA7075-T6",
        "E_MPa": 71000,
        "H_prime_MPa": 977,
        "n_prime": 0.106,
        "stress_max_MPa": 521,
        "reference_csv": str(REFERENCE_CURVE_DIR / "aa7075-T6_monotonic_ROM_cyclic_parameters.csv"),
        "plot_label": "AA7075-T6 cyclic ROM",
    },
    "AA2024-T351": {
        "name": "AA2024-T351",
        "E_MPa": 73100,
        "H_prime_MPa": 662,
        "n_prime": 0.070,
        "stress_max_MPa": 449,
        "reference_csv": str(REFERENCE_CURVE_DIR / "aa2024-T351_monotonic_ROM_1pct_strain.csv"),
        "plot_label": "AA2024-T351 cyclic ROM",
    },
    "AA7075-T651": {
        "name": "AA7075-T651",
        "E_MPa": 70000,
        "H_prime_MPa": 852,
        "n_prime": 0.074,
        "stress_max_MPa": 543,
        "reference_csv": str(REFERENCE_CURVE_DIR / "aa7075-T651_monotonic_ROM_cyclic_parameters.csv"),
        "plot_label": "AA7075-T651 cyclic ROM",
    },
}


def _clean_material_name(material_name):
    return str(material_name).strip()


def get_reference_material(material_name):
    """Return a copy of the Ramberg-Osgood reference material entry."""
    clean_name = _clean_material_name(material_name)
    try:
        return dict(REFERENCE_MATERIALS[clean_name])
    except KeyError as exc:
        available = ", ".join(sorted(REFERENCE_MATERIALS))
        raise ValueError(
            f"Unknown reference_material '{clean_name}'. Available options: {available}"
        ) from exc


def _format_e(E_MPa):
    E_float = float(E_MPa)
    if E_float.is_integer():
        return str(int(E_float))
    return str(E_float)


def _is_auto(value):
    return isinstance(value, str) and value.strip().lower() == "auto"


def resolve_abaqus_reference_material(abaqus):
    """Resolve <reference_material> and <E> auto in an Abaqus settings dict.

    If no reference_material is present, the input dictionary is returned unchanged.
    If reference_material is present and E is "auto", E is replaced with the
    material's Ramberg-Osgood elastic modulus.  If E is explicit, it must match
    the reference material modulus so the simulation and comparison curve have
    the same elastic baseline.
    """
    reference_material = abaqus.get("reference_material")
    if reference_material is None or str(reference_material).strip() == "":
        return abaqus

    ref = get_reference_material(reference_material)
    expected_e = float(ref["E_MPa"])
    current_e = abaqus.get("E")

    if current_e is None or _is_auto(current_e):
        abaqus["E"] = int(expected_e) if expected_e.is_integer() else expected_e
    else:
        actual_e = float(current_e)
        if abs(actual_e - expected_e) > 1e-9:
            raise ValueError(
                f"reference_material {ref['name']} expects E = {_format_e(expected_e)} MPa, "
                f"but the input file gives E = {_format_e(actual_e)} MPa. "
                "Use <E> auto </E> or change E only for an intentional elastic-modulus study."
            )
        abaqus["E"] = int(actual_e) if actual_e.is_integer() else actual_e

    abaqus["reference_material"] = ref["name"]
    abaqus["reference_material_properties"] = ref
    abaqus["reference_curve_csv"] = ref["reference_csv"]
    abaqus["reference_plot_label"] = ref["plot_label"]
    return abaqus


def resolve_abaqus_reference_material_xml(root):
    """Resolve <reference_material> metadata directly in an XML root."""
    abaqus_element = root.find("abaqus")
    if abaqus_element is None:
        return root

    reference_material_text = abaqus_element.findtext("reference_material")
    if reference_material_text is None or not reference_material_text.strip():
        return root

    ref = get_reference_material(reference_material_text)
    expected_e = float(ref["E_MPa"])
    e_element = abaqus_element.find("E")
    current_e = e_element.text.strip() if e_element is not None and e_element.text else None

    if e_element is None:
        e_element = ET.SubElement(abaqus_element, "E")

    if current_e is None or _is_auto(current_e):
        e_element.text = f" {_format_e(expected_e)} "
    else:
        actual_e = float(current_e)
        if abs(actual_e - expected_e) > 1e-9:
            raise ValueError(
                f"reference_material {ref['name']} expects E = {_format_e(expected_e)} MPa, "
                f"but the input file gives E = {_format_e(actual_e)} MPa. "
                "Use <E> auto </E> or change E only for an intentional elastic-modulus study."
            )
        e_element.text = f" {_format_e(actual_e)} "

    _set_child_text(abaqus_element, "reference_material", f" {ref['name']} ")
    _set_child_text(abaqus_element, "reference_curve_csv", f" {ref['reference_csv']} ")
    _set_child_text(abaqus_element, "reference_plot_label", f" {ref['plot_label']} ")
    _set_child_text(abaqus_element, "reference_H_prime_MPa", f" {_format_e(ref['H_prime_MPa'])} ")
    _set_child_text(abaqus_element, "reference_n_prime", f" {ref['n_prime']} ")
    _set_child_text(abaqus_element, "reference_stress_max_MPa", f" {_format_e(ref['stress_max_MPa'])} ")
    return root


def _set_child_text(parent, tag, text):
    child = parent.find(tag)
    if child is None:
        child = ET.SubElement(parent, tag)
    child.text = text
    return child


# Imported at the bottom so the helper can be loaded by tests before use.
import xml.etree.ElementTree as ET
