"""Read-only inventory of original ODB instances and actual saved frames.

Run with Abaqus Python from the original abaqus_files directory. ODB_FILE may
be a stem or filename; otherwise exactly one .odb file must be present.
ODB_INVENTORY_OUTPUT overrides the default ../odb_inventory.json destination.
No backup restoration, ROI set creation, save or writable open is performed.
"""
from __future__ import print_function

import json
import os
import sys


def export_odb_inventory(odb_path, output_path):
    """Open the original database read-only and write a JSON frame inventory."""
    from odbAccess import openOdb

    odb_path = os.path.abspath(odb_path)
    if not isinstance(odb_path, str):
        odb_path = odb_path.encode(sys.getfilesystemencoding() or "utf-8")
    odb = openOdb(path=odb_path, readOnly=True)
    try:
        instances = []
        for name in odb.rootAssembly.instances.keys():
            instance = odb.rootAssembly.instances[name]
            xs = [float(node.coordinates[0]) for node in instance.nodes]
            ys = [float(node.coordinates[1]) for node in instance.nodes]
            instances.append({"name": name, "nodes": len(instance.nodes),
                              "elements": len(instance.elements),
                              "element_types": sorted(set(element.type for element in instance.elements)),
                              "bounds": [min(xs), max(xs), min(ys), max(ys)] if xs else None})
        steps = []
        for name in odb.steps.keys():
            frames = []
            for index, frame in enumerate(odb.steps[name].frames):
                fields = list(frame.fieldOutputs.keys())
                components = {}
                for field_name in fields:
                    labels = getattr(frame.fieldOutputs[field_name], "componentLabels", ())
                    if labels:
                        components[field_name] = list(labels)
                frames.append({"index": index, "time": float(frame.frameValue),
                               "increment": int(frame.incrementNumber), "fields": fields,
                               "component_labels": components})
            steps.append({"name": name, "frames": frames})
        record = {"odb": odb_path, "instances": instances, "steps": steps}
        with open(output_path, "w") as handle:
            json.dump(record, handle, indent=2)
        return record
    finally:
        odb.close()


def main():
    """Select the source without guessing among multiple ODBs."""
    source = os.environ.get("ODB_FILE")
    if source:
        if not source.lower().endswith(".odb"):
            source += ".odb"
    else:
        candidates = sorted(name for name in os.listdir(os.getcwd()) if name.lower().endswith(".odb"))
        if len(candidates) != 1:
            raise ValueError("Set ODB_FILE or provide exactly one ODB; found %s." % candidates)
        source = candidates[0]
    output = os.path.abspath(os.environ.get("ODB_INVENTORY_OUTPUT", "../odb_inventory.json"))
    export_odb_inventory(os.path.abspath(source), output)
    print("Wrote read-only inventory: " + output)


if __name__ == "__main__":
    main()
