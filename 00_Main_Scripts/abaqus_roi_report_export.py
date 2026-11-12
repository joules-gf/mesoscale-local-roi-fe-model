"""Export Abaqus field reports for border regions of interest (ROIs).

This is the cleaned-up replacement for the old replay-generated
``createCrackData`` scripts.  The old scripts manually selected element sets in
Abaqus and called them cracks.  In this workflow we call them ROIs.

Julio's manual selection pattern, translated into code:

1. Start on the right border near the top of the domain.
2. Move 0.1 domain units down.
3. Select the elements in the half-circle inside the domain by moving 0.1 units
   left from the border point.
4. Repeat down the right side for nine ROIs total.
5. Repeat from the left border, except the half-circle points right.

This file intentionally avoids modern Python-only syntax because Abaqus/CAE can
run an older Python interpreter.  Keep the script readable and conservative.
"""

from __future__ import print_function

import csv
import json
import math
import os
import shutil
import sys


def abaqus_native_string(value):
    """Convert JSON text to the native string required by Abaqus Python 2 APIs.

    Preserve existing byte strings; encode unicode with the filesystem encoding
    (mbcs on Windows), not Python 2's implicit ASCII conversion. Python 3 APIs
    continue to receive text strings.
    """
    if isinstance(value, str):
        return str(value)
    return value.encode(sys.getfilesystemencoding() or "utf-8")


DEFAULT_INSTANCE_NAME = "DOMAIN-1"
DEFAULT_REPORT_VARIABLES = (
    ("S", "S22"),
    ("PE", "PE22"),
)


class ROIRegion(object):
    """A half-circular border ROI."""

    def __init__(self, name, side, center, radius):
        self.name = name
        self.side = side
        self.center = center
        self.radius = radius

    def contains_centroid(self, centroid):
        """Return True when an element centroid belongs to this ROI."""
        x_value = float(centroid[0])
        y_value = float(centroid[1])
        center_x, center_y = self.center
        distance = math.sqrt((x_value - center_x) ** 2 + (y_value - center_y) ** 2)
        inside_circle = distance <= self.radius
        if self.side == "right":
            inside_domain_half = x_value <= center_x
        else:
            inside_domain_half = x_value >= center_x
        return inside_circle and inside_domain_half


def build_edge_roi_specs(width, height, radius=0.1, count_per_side=9, vertical_spacing=None, x_min=0.0, y_min=0.0):
    """Build right-border then left-border ROI definitions.

    ``width`` and ``height`` describe the domain size.  ``x_min`` and ``y_min``
    describe where that domain starts in the ODB coordinates.  This matters
    because Abaqus meshes are not guaranteed to start at (0, 0).
    """
    if vertical_spacing is None:
        vertical_spacing = radius

    x_max = x_min + width
    y_max = y_min + height

    specs = []
    for index in range(count_per_side):
        y_value = y_max - radius - (index * vertical_spacing)
        specs.append(ROIRegion("roi_right_%02d" % (index + 1), "right", (x_max, y_value), radius))
    for index in range(count_per_side):
        y_value = y_max - radius - (index * vertical_spacing)
        specs.append(ROIRegion("roi_left_%02d" % (index + 1), "left", (x_min, y_value), radius))
    return specs


def element_centroid(element, node_coordinates_by_label=None):
    """Return the centroid of an Abaqus element from its connected node coords."""
    if node_coordinates_by_label is None and hasattr(element, "getNodes"):
        coordinates = [node.coordinates for node in element.getNodes()]
    else:
        coordinates = [node_coordinates_by_label[label] for label in element.connectivity]
    count = float(len(coordinates))
    centroid = []
    for axis in range(3):
        
        total = 0.0
        for coord in coordinates:
            total += coord[axis]
        centroid.append(total / count)
    return tuple(centroid)


def group_element_labels_by_roi(elements, roi_specs, node_coordinates_by_label=None):
    """Map each ROI name to the labels of elements whose centroids fall inside it."""
    labels_by_roi = dict((roi.name, []) for roi in roi_specs)
    for element in elements:
        centroid = element_centroid(element, node_coordinates_by_label)
        for roi in roi_specs:
            if roi.contains_centroid(centroid):
                labels_by_roi[roi.name].append(element.label)
    return labels_by_roi


def infer_domain_bounds_from_instance(instance):
    """Infer domain bounds from instance node coordinates."""
    x_values = [float(node.coordinates[0]) for node in instance.nodes]
    y_values = [float(node.coordinates[1]) for node in instance.nodes]
    return min(x_values), max(x_values), min(y_values), max(y_values)


def infer_domain_size_from_instance(instance):
    """Infer domain width/height from instance node coordinates."""
    x_min, x_max, y_min, y_max = infer_domain_bounds_from_instance(instance)
    return x_max - x_min, y_max - y_min


def choose_instance(odb, preferred_name=DEFAULT_INSTANCE_NAME):
    """Return the preferred instance, or the only available instance as fallback."""
    preferred_name = abaqus_native_string(preferred_name)
    instances = odb.rootAssembly.instances
    if preferred_name in instances.keys():
        return preferred_name, instances[preferred_name]
    names = list(instances.keys())
    if len(names) == 1:
        return abaqus_native_string(names[0]), instances[names[0]]
    raise KeyError("Could not find instance %s. Available instances: %s" % (preferred_name, names))


def existing_roi_set_names(assembly, roi_specs):
    """Return ROI element sets that already exist in the ODB."""
    existing = assembly.elementSets.keys()
    found = []
    for roi in roi_specs:
        if roi.name in existing:
            found.append(roi.name)
        elif roi.name.upper() in existing:
            found.append(roi.name.upper())
    return found


def require_no_existing_roi_sets(assembly, roi_specs):
    """Fail early if this ODB already contains ROI sets.

    Abaqus ODB element-set repositories do not support deleting sets once they
    have been added.  I intentionally fail here instead of creating suffixes like
    ``_current`` so the ODB only ever has the clean ROI names.

    If this message appears, start from a clean ODB generated before ROI export
    was run, or rerun the simulation to create a fresh ODB.
    """
    found = existing_roi_set_names(assembly, roi_specs)
    if found:
        raise RuntimeError(
            "This ODB already contains ROI element sets and Abaqus does not "
            "allow deleting them from the ODB repository. Existing sets: %s. "
            "Please use a clean ODB generated before ROI export, or rerun the "
            "simulation to create a fresh ODB."
            % ", ".join(found)
        )


def create_roi_sets(odb, roi_specs, instance_name=DEFAULT_INSTANCE_NAME):
    """Create cleanly named ODB element sets for the requested ROIs."""
    assembly = odb.rootAssembly
    require_no_existing_roi_sets(assembly, roi_specs)

    instance_name, instance = choose_instance(odb, instance_name)
    node_coordinates_by_label = dict((node.label, node.coordinates) for node in instance.nodes)
    labels_by_roi = group_element_labels_by_roi(instance.elements, roi_specs, node_coordinates_by_label)
    set_name_by_roi = {}

    for roi_name, labels in labels_by_roi.items():
        if not labels:
            print("Warning: ROI %s has no elements. Check domain size/radius/spacing." % roi_name)
            continue
        assembly.ElementSetFromElementLabels(
            name=roi_name,
            elementLabels=((instance_name, tuple(labels)),),
        )
        set_name_by_roi[roi_name] = roi_name
    odb.save()
    return set_name_by_roi


def resolve_element_set_name(assembly, requested_name):
    """Find the ODB repository key for an element set name."""
    if requested_name in assembly.elementSets.keys():
        return requested_name
    upper_name = requested_name.upper()
    if upper_name in assembly.elementSets.keys():
        return upper_name
    return None

def export_roi_field_reports(odb, roi_specs, frames, output_folder=".", set_name_by_roi=None):
    """Export S22/PE22 field reports for each ROI at the selected frames."""
    import visualization
    from abaqus import session
    from abaqusConstants import COMMA_SEPARATED_VALUES, COMPONENT, INTEGRATION_POINT, OFF, SPECIFY
    import displayGroupOdbToolset as dgo

    if set_name_by_roi is None:
        set_name_by_roi = {}

    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    viewport_name = "Viewport: 1"
    if viewport_name not in session.viewports.keys():
        viewport = session.Viewport(name=viewport_name)
    else:
        viewport = session.viewports[viewport_name]
    viewport.setValues(displayedObject=odb)

    if hasattr(session, "fieldReportOptions"):
        session.fieldReportOptions.setValues(reportFormat=COMMA_SEPARATED_VALUES)

    variables = tuple(
        (field_name, INTEGRATION_POINT, ((COMPONENT, component_name),))
        for field_name, component_name in DEFAULT_REPORT_VARIABLES
    )

    for frame_number in frames:
        for roi in roi_specs:
            requested_set_name = set_name_by_roi.get(roi.name, roi.name)
            element_set_name = resolve_element_set_name(odb.rootAssembly, requested_set_name)
            if element_set_name is None:
                print("Skipping %s because no element set was created." % roi.name)
                continue
            leaf = dgo.LeafFromElementSets(elementSets=(element_set_name,))
            display_group = session.DisplayGroup(name="dg_" + roi.name, leaf=leaf)
            viewport.odbDisplay.setValues(visibleDisplayGroups=(display_group,))
            report_name = os.path.join(output_folder, "%s_frame%d.csv" % (roi.name, int(frame_number)))
            session.writeFieldReport(
                fileName=abaqus_native_string(report_name),
                append=OFF,
                sortItem="Element Label",
                odb=odb,
                step=0,
                frame=int(frame_number),
                outputPosition=INTEGRATION_POINT,
                variable=variables,
                stepFrame=SPECIFY,
            )

def export_domain_pe22_summary(odb, frames, output_folder, instance_name="I-PART-1"):
    """Write signed, unweighted CPS3 PE22 integration-point statistics.

    Use precisely the first-step frame indices used by the ROI reports. No
    elastic subtraction, clipping, absolute value or area weighting is applied.
    Reference-node-only instances are excluded; multiple meshed instances fail
    rather than silently changing the meaning of the whole-model mean.
    """
    from abaqusConstants import INTEGRATION_POINT

    instances = odb.rootAssembly.instances
    model_names = [name for name in instances.keys() if len(instances[name].elements)]
    if len(model_names) != 1:
        raise ValueError("Domain PE22 requires a single meshed model instance: %s" % model_names)
    chosen_name, instance = choose_instance(odb, instance_name)
    if chosen_name != model_names[0]:
        raise ValueError("Selected PE22 instance must be the one meshed model instance.")
    elements = instance.elements
    if any(element.type != "CPS3" for element in elements):
        raise ValueError("Domain PE22 summary requires CPS3 elements (one integration point each).")
    expected_labels = set(element.label for element in elements)
    step_names = list(odb.steps.keys())
    if not step_names:
        raise ValueError("ODB has no first step for PE22 summary.")
    step = odb.steps[step_names[0]]
    if not frames:
        raise ValueError("Domain PE22 requires selected frame indices.")
    rows = []
    for frame_number in frames:
        index = int(frame_number)
        if index != frame_number or index < 0 or index >= len(step.frames):
            raise ValueError("Invalid first-step PE22 frame index: %s" % frame_number)
        frame = step.frames[index]
        if "PE" not in frame.fieldOutputs.keys():
            raise ValueError("Frame %d has no PE field; direct PE22 is required." % index)
        pe_field = frame.fieldOutputs["PE"]
        if "PE22" not in pe_field.componentLabels:
            raise ValueError("Frame %d PE component labels do not contain PE22." % index)
        scalar = pe_field.getSubset(region=instance).getScalarField(componentLabel="PE22")
        values = []
        labels = set()
        for point in scalar.values:
            if point.instance.name != chosen_name or point.position != INTEGRATION_POINT:
                raise ValueError("PE22 point is outside the selected instance/integration points.")
            if point.elementLabel not in expected_labels or point.elementLabel in labels or point.integrationPoint != 1:
                raise ValueError("PE22 must contain exactly one integration point per CPS3 element.")
            value = float(point.data)
            if math.isnan(value) or math.isinf(value):
                raise ValueError("Nonfinite PE22 at frame %d element %d." % (index, point.elementLabel))
            labels.add(point.elementLabel)
            values.append(value)
        if labels != expected_labels or not values:
            raise ValueError("Missing PE22 integration points in selected model instance.")
        step_time = float(frame.frameValue)
        if math.isnan(step_time) or math.isinf(step_time):
            raise ValueError("Nonfinite PE22 frame time.")
        # CAE may shadow bare sum with a kernel numeric function that rejects
        # generators. Count signs without invoking that injected function.
        rows.append((index, step_time, chosen_name, math.fsum(values) / len(values),
                     min(values), max(values), len([value for value in values if value < 0.0]),
                     len([value for value in values if value == 0.0]),
                     len([value for value in values if value > 0.0]), len(values)))
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)
    output_path = os.path.join(output_folder, "domain_pe22_summary.csv")
    # Python 2's csv writer needs a binary stream on Windows; Python 3 needs
    # newline='' to avoid doubled line endings.
    if sys.version_info[0] < 3:
        handle = open(output_path, "wb")
    else:
        handle = open(output_path, "w", newline="")
    try:
        writer = csv.writer(handle)
        writer.writerow(("frame_number", "step_time", "instance_name", "average_plastic_strain",
                         "min_pe22", "max_pe22", "negative_count", "zero_count", "positive_count", "point_count"))
        writer.writerows(rows)
    finally:
        handle.close()
    return output_path


def load_config(config_path="roi_report_config.json"):
    """Load optional JSON config from the Abaqus working directory."""
    if not os.path.isfile(config_path):
        return {}
    with open(config_path, "r") as config_file:
        return json.load(config_file)


def find_odb_file(config):
    if config.get("odb_path"):
        return abaqus_native_string(os.path.abspath(config["odb_path"]))
    odb_files = sorted(name for name in os.listdir(os.getcwd()) if name.lower().endswith(".odb"))
    if not odb_files:
        raise IOError("No ODB file found in the Abaqus working directory.")
    return abaqus_native_string(os.path.abspath(odb_files[0]))


def clean_backup_path_for_odb(odb_path):
    root, extension = os.path.splitext(odb_path)
    return root + "_clean_before_roi" + extension


def restore_clean_odb_if_available(odb_path, config):
    """Restore the pre-ROI ODB backup so ROI sets are regenerated from scratch."""
    if config.get("reset_from_clean_backup", True) is False:
        return
    backup_path = clean_backup_path_for_odb(odb_path)
    if os.path.isfile(backup_path):
        print("Restoring clean ODB before regenerating ROI sets: %s" % backup_path)
        shutil.copyfile(backup_path, odb_path)


def save_clean_odb_backup_if_missing(odb_path, config):
    """Save a clean ODB copy before adding ROI sets for the first time."""
    if config.get("save_clean_backup", True) is False:
        return
    backup_path = clean_backup_path_for_odb(odb_path)
    if not os.path.isfile(backup_path):
        print("Saving clean ODB backup before ROI sets are added: %s" % backup_path)
        shutil.copyfile(odb_path, backup_path)



def main():
    """Abaqus noGUI entry point."""
    config = load_config()
    # Reject missing/malformed frame selections before restoring or opening an
    # ODB. Frame bounds still need to be checked against the chosen database.
    frames = [int(frame) for frame in config.get("frames", [])]
    if not frames:
        raise ValueError("roi_report_config.json must provide a non-empty 'frames' list.")

    from abaqus import session

    odb_path = find_odb_file(config)

    # This is the clean replacement for the old ``_current`` suffix idea:
    # keep a pre-ROI ODB backup, restore it before every ROI export, and then
    # recreate the ROI sets with the same readable names.
    restore_clean_odb_if_available(odb_path, config)

    odb = session.openOdb(name=odb_path, readOnly=False)

    instance_name = config.get("instance_name", DEFAULT_INSTANCE_NAME)
    instance_name, instance = choose_instance(odb, instance_name)
    if config.get("domain_size"):
        width, height = config["domain_size"]
        x_min = float(config.get("x_min", 0.0))
        y_min = float(config.get("y_min", 0.0))
    else:
        x_min, x_max, y_min, y_max = infer_domain_bounds_from_instance(instance)
        width = x_max - x_min
        height = y_max - y_min

    print("ROI domain bounds: x_min=%s, width=%s, y_min=%s, height=%s" % (x_min, width, y_min, height))
    roi_specs = build_edge_roi_specs(
        width=float(width),
        height=float(height),
        radius=float(config.get("radius", 0.1)),
        count_per_side=int(config.get("count_per_side", 9)),
        vertical_spacing=float(config["vertical_spacing"]) if "vertical_spacing" in config else None,
        x_min=float(x_min),
        y_min=float(y_min),
    )

    # Verify the ODB is clean before saving the backup.  If ROI sets already
    # exist and no clean backup is available, Abaqus cannot delete them; rerun
    # the simulation or provide a clean ODB.
    require_no_existing_roi_sets(odb.rootAssembly, roi_specs)
    odb.close()
    save_clean_odb_backup_if_missing(odb_path, config)

    odb = session.openOdb(name=odb_path, readOnly=False)
    output_folder = config.get("output_folder", "../roi_reports_pe22")
    set_name_by_roi = create_roi_sets(odb, roi_specs, instance_name=instance_name)
    export_roi_field_reports(odb, roi_specs, frames, output_folder=output_folder, set_name_by_roi=set_name_by_roi)
    export_domain_pe22_summary(odb, frames, output_folder, instance_name=instance_name)
    odb.close()


if __name__ == "__main__":
    main()
