"""Export individual survey objects without splitting a sample's analyses."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .geophysical_observations import GEOPHYSICAL_DIRECTORIES, GEOPHYSICAL_TABLES
from .observation_sources import BOREHOLE_SOURCE_KINDS, borehole_source_kind


OBJECT_TABLES = {
    "boreholes": ("hole_id", ("borehole_collars", "borehole_lithology")),
    "downhole_gamma": ("hole_id", ("downhole_gamma",)),
    "downhole_magnetic": ("hole_id", ("downhole_magnetic",)),
    "trenches": ("trench_id", ("trenches", "trench_intervals")),
    "borehole_samples": ("sample_id", ("borehole_assays",)),
    "trench_samples": ("sample_id", ("trench_samples",)),
    "surface_samples": ("sample_id", ("surface_geochemistry",)),
    "outcrop_observations": ("observation_id", ("outcrop_observations",)),
    "terrain_observations": ("observation_id", ("terrain_observations",)),
    **{table: ("observation_id", (table,)) for table in GEOPHYSICAL_TABLES.values()},
    "quality_control_samples": ("sample_id", ("quality_control",)),
    "structural_observations": ("observation_id", ("structural_observations", "fault_intersections")),
}
CONTROL_FOLDERS = {"duplicate": "duplicates", "blank": "blanks", "standard": "standards"}


def _sample_interval(row: dict[str, Any]) -> tuple[str, float, float]:
    return row["hole_id"], row["from_m"], row["to_m"]


def _object_names(identifiers: Iterable[str]) -> dict[str, str]:
    used_names = set()
    names = {}
    for identifier in identifiers:
        name = identifier.casefold()
        if (not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", identifier)
                or re.fullmatch(r"con|prn|aux|nul|(?:com|lpt)[0-9]", name)
                or name in used_names):
            names[identifier] = f"~{sha256(identifier.encode('utf-8')).hexdigest()}"
        else:
            used_names.add(name)
            names[identifier] = identifier
    return names


def _object_layout(groups: dict, collars: list[dict]):
    names = {kind: _object_names(objects) for kind, objects in groups.items()}
    borehole_kinds = {row["hole_id"]: borehole_source_kind(row) for row in collars}
    folders = {
        "boreholes": {identifier: f"{borehole_kinds.get(identifier, 'boreholes')}/{name}"
                      for identifier, name in names["boreholes"].items()},
        "trenches": {identifier: f"trenches/{name}" for identifier, name in names["trenches"].items()},
    }
    paths = {kind: {identifier: f"{folder}/{names[kind][identifier]}.json" for identifier, folder in entries.items()}
             for kind, entries in folders.items()}
    for kind, folder in (("surface_samples", "surface_geochemistry"), ("outcrop_observations", "outcrops"),
                         ("terrain_observations", "terrain"), *GEOPHYSICAL_DIRECTORIES.items()):
        paths[kind] = {identifier: f"{folder}/{name}.json" for identifier, name in names[kind].items()}
    paths["quality_control_samples"] = {}
    for identifier, name in names["quality_control_samples"].items():
        control = groups["quality_control_samples"][identifier]["quality_control"][0]
        folder = CONTROL_FOLDERS.get(control["qc_type"], "other")
        paths["quality_control_samples"][identifier] = f"quality_control/{folder}/{name}.json"

    links = defaultdict(list)
    for kind, parent, key, subfolder, link_field, standalone in (
        ("borehole_samples", "boreholes", "hole_id", "samples", "sample_files", "borehole_samples"),
        ("trench_samples", "trenches", "trench_id", "samples", "sample_files", "trench_samples"),
        ("structural_observations", "boreholes", "hole_id", "structures", "structural_files", "surface_structures"),
        ("downhole_gamma", "boreholes", "hole_id", "gamma_log", "gamma_log_files", "gamma_logs"),
        ("downhole_magnetic", "boreholes", "hole_id", "magnetic_log", "magnetic_log_files", "magnetic_logs"),
    ):
        paths[kind] = {}
        for identifier, data in groups[kind].items():
            parent_id = next(iter(data.values()))[0][key]
            parent_folder = folders[parent].get(parent_id)
            folder = f"{parent_folder}/{subfolder}" if parent_folder else standalone
            path = f"{folder}/{names[kind][identifier]}.json"
            paths[kind][identifier] = path
            if parent_folder:
                links[parent, parent_id, link_field].append(path)
    return paths, links


def _write_objects(bundle: dict[str, Any], directory: Path) -> None:
    tables = bundle["tables"]
    groups = {}
    for kind, (key, names) in OBJECT_TABLES.items():
        objects = groups[kind] = defaultdict(dict)
        for name in names:
            for row in tables.get(name, []):
                objects[row[key]].setdefault(name, []).append(row)

    core_samples = groups["borehole_samples"]
    samples_by_interval = {_sample_interval(data["borehole_assays"][0]): data for data in core_samples.values()}
    for row in tables.get("downhole_properties", []):
        sample = samples_by_interval.get(_sample_interval(row))
        if sample is None:
            sample = groups["boreholes"][row["hole_id"]]
        sample.setdefault("downhole_properties", []).append(row)

    paths, links = _object_layout(groups, tables.get("borehole_collars", []))
    if bundle.get("stage") != "preliminary":
        for folder in (*BOREHOLE_SOURCE_KINDS, "trenches", "surface_geochemistry", "quality_control"):
            (directory / folder).mkdir(parents=True)

    metadata = {"schema_version": bundle["schema_version"], "campaign_id": bundle["campaign"]["campaign_id"]}
    for kind, objects in groups.items():
        for identifier, data in objects.items():
            record = {**metadata, "data_kind": "exploration_observation_object",
                      "kind": kind, "object_id": identifier, "tables": data}
            if kind in {"boreholes", "trenches"}:
                record["sample_files"] = links.get((kind, identifier, "sample_files"), [])
            if kind == "boreholes":
                record["structural_files"] = links.get((kind, identifier, "structural_files"), [])
                record["gamma_log_files"] = links.get((kind, identifier, "gamma_log_files"), [])
                record["magnetic_log_files"] = links.get((kind, identifier, "magnetic_log_files"), [])
            output = directory / paths[kind][identifier]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8",
            )

    manifest = {key: bundle[key] for key in ("schema_version", "campaign", "plan", "rock_catalog", "table_fields")}
    manifest.update(data_kind="exploration_observation_object_index", objects=paths)
    (directory / "index.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8",
    )


def save_observation_objects(bundle: dict[str, Any], directory: Path) -> Path:
    """Replace the individual export after preparing a complete new copy."""
    destination = directory / "objects"
    with TemporaryDirectory(prefix=".observation-objects-", dir=directory) as work:
        pending = Path(work) / "new"
        previous = Path(work) / "previous"
        _write_objects(bundle, pending)
        if destination.exists():
            destination.rename(previous)
        try:
            pending.rename(destination)
        except OSError:
            if previous.exists():
                previous.rename(destination)
            raise
    return destination / "index.json"
