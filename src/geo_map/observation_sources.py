"""Independent public data sources for vertical and inclined drilling."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


BOREHOLE_SOURCE_TABLES = (
    "borehole_collars", "borehole_lithology", "borehole_assays", "downhole_properties",
    "structural_observations", "fault_intersections", "downhole_gamma", "downhole_magnetic",
)
BOREHOLE_SOURCE_KINDS = {
    "vertical_boreholes": "Вертикальное бурение",
    "inclined_boreholes": "Наклонное бурение",
}


def borehole_source_kind(collar: dict[str, Any]) -> str:
    return "vertical_boreholes" if collar["dip_deg"] == -90 else "inclined_boreholes"


def describe_borehole_sources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe disjoint sources without duplicating their records in the bundle."""
    sources = []
    table_names = [name for name in BOREHOLE_SOURCE_TABLES if name in bundle["table_fields"]]
    for kind, title in BOREHOLE_SOURCE_KINDS.items():
        holes = [row for row in bundle["tables"]["borehole_collars"] if borehole_source_kind(row) == kind]
        ids = {row["hole_id"] for row in holes}
        tables = {name: [row for row in bundle["tables"].get(name, []) if row["hole_id"] in ids]
                  for name in table_names}
        sources.append({
            "source_id": f"{bundle['campaign']['campaign_id']}:{kind}",
            "kind": kind, "title": title, "directory": f"sources/{kind}",
            "hole_ids": [row["hole_id"] for row in holes],
            "table_names": table_names,
            "summary": {
                "hole_count": len(holes), "drilled_m": round(sum(row["total_depth_m"] for row in holes), 6),
                "sample_count": len({row["sample_id"] for row in tables["borehole_assays"]}),
                "assay_count": len(tables["borehole_assays"]),
                "lithology_count": len(tables["borehole_lithology"]),
                "property_count": len(tables["downhole_properties"]),
                "gamma_log_count": len(tables.get("downhole_gamma", ())),
                "magnetic_log_count": len(tables.get("downhole_magnetic", ())),
                "contact_count": sum(row["feature_type"] == "contact" for row in tables["structural_observations"]),
                "fault_observation_count": len(tables["fault_intersections"]),
            },
        })
    return sources


def make_borehole_source(bundle: dict[str, Any], kind: str) -> dict[str, Any]:
    """Build a standalone source from observations only, without ground truth."""
    source = next((item for item in describe_borehole_sources(bundle) if item["kind"] == kind), None)
    if source is None:
        raise ValueError(f"Неизвестный источник бурения: {kind}")
    ids = set(source["hole_ids"])
    tables = {name: [row for row in bundle["tables"].get(name, []) if row["hole_id"] in ids]
              for name in source["table_names"]}
    rock_ids = {row["observed_rock_id"] for row in tables["borehole_lithology"]}
    return deepcopy({
        "schema_version": bundle["schema_version"], "data_kind": "borehole_observation_source",
        "source": source, "campaign": bundle["campaign"], "plan": bundle["plan"],
        "summary": source["summary"], "notes": bundle["notes"],
        "rock_catalog": [rock for rock in bundle["rock_catalog"] if rock["id"] in rock_ids],
        "table_fields": {name: bundle["table_fields"][name] for name in source["table_names"]},
        "tables": tables,
    })
