"""Independent observation tables for the two geophysical channels."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from .geophysics import CHANNELS


GEOPHYSICAL_TABLES = {"magnetic": "magnetic_observations", "gamma": "gamma_observations"}
GEOPHYSICAL_PREFIXES = {"magnetic": "MAG", "gamma": "GAM"}
GEOPHYSICAL_DIRECTORIES = {table: f"geophysics/{method}" for method, table in GEOPHYSICAL_TABLES.items()}
LEGACY_GEOPHYSICAL_TABLE = "geophysical_observations"
GEOPHYSICAL_TABLE_FIELDS = {
    GEOPHYSICAL_TABLES[method]: [
        *"campaign_id observation_id station_id x_m y_m surface_elevation_m".split(),
        field, sigma, *"position_uncertainty_m observation_method survey_date".split(),
    ]
    for method, (field, sigma) in CHANNELS.items()
}


def geophysical_rows(tables, method):
    name = GEOPHYSICAL_TABLES[method]
    if name in tables:
        return tables[name]
    field, _ = CHANNELS[method]
    return [
        {key: row.get(key) if key != "station_id" else row.get("station_id", row["observation_id"])
         for key in GEOPHYSICAL_TABLE_FIELDS[name]}
        for row in tables.get(LEGACY_GEOPHYSICAL_TABLE, ())
        if row.get(field) is not None
    ]


def point_geojson(name, rows, dimensions):
    return {
        "type": "FeatureCollection", "schema_version": "1.0", "name": name,
        "coordinate_system": "local_cartesian", "coordinate_unit": "m",
        "map_extent_m": {"x": [0, dimensions["width_m"]], "y": [0, dimensions["height_m"]]},
        "features": [
            {"type": "Feature", "id": row["observation_id"],
             "geometry": {"type": "Point", "coordinates": [row["x_m"], row["y_m"]]},
             "properties": {key: value for key, value in row.items() if key not in {"x_m", "y_m"}}}
            for row in rows
        ],
    }


def split_legacy_geophysical_bundle(bundle):
    """Expose older combined records as two tables, preserving their original references."""
    source = bundle["tables"]
    if LEGACY_GEOPHYSICAL_TABLE not in source:
        return bundle
    tables = dict(source)
    fields = dict(bundle["table_fields"])
    layers = dict(bundle.get("geojson", {}))
    for item in (tables, fields, layers):
        item.pop(LEGACY_GEOPHYSICAL_TABLE, None)
    for method, table in GEOPHYSICAL_TABLES.items():
        tables[table] = geophysical_rows(source, method)
        fields[table] = GEOPHYSICAL_TABLE_FIELDS[table]
        layers[table] = point_geojson(table, tables[table], bundle["campaign"])
    summary = {**bundle["summary"], **{f"{method}_observation_count": len(tables[table])
                                     for method, table in GEOPHYSICAL_TABLES.items()}}
    return {**bundle, "schema_version": "1.7", "tables": tables, "table_fields": fields, "geojson": layers, "summary": summary}


def load_geophysical_csv(path: Path, method: str, campaign_id: str):
    """Read one measured channel from its CSV template."""
    field, sigma = CHANNELS[method]
    fields = GEOPHYSICAL_TABLE_FIELDS[GEOPHYSICAL_TABLES[method]]
    required = {"campaign_id", "observation_id", "x_m", "y_m", field}
    numeric = ("x_m", "y_m", "surface_elevation_m", field, sigma, "position_uncertainty_m")
    rows = []
    seen = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not required.issubset(reader.fieldnames or ()):
            raise ValueError(f"{path}: отсутствуют обязательные поля канала {method}")
        for source in reader:
            location = f"{path}:{reader.line_num}"
            row = {key: (source.get(key) or "").strip() or None for key in fields}
            identifier = row["observation_id"]
            if row["campaign_id"] != campaign_id or not identifier or identifier in seen:
                raise ValueError(f"{location}: неверная экспедиция или повторяющийся либо пустой идентификатор наблюдения")
            row["station_id"] = row["station_id"] or identifier
            for key in numeric:
                try:
                    value = float(row[key]) if row[key] is not None else None
                except ValueError as error:
                    raise ValueError(f"{location}: некорректное числовое поле {key}") from error
                if (value is None and key in required) or (value is not None and not math.isfinite(value)):
                    raise ValueError(f"{location}: некорректное числовое поле {key}")
                if key in {sigma, "position_uncertainty_m", "gamma_count_rate_cps"} and value is not None and value < 0:
                    raise ValueError(f"{location}: поле {key} должно быть неотрицательным")
                row[key] = value
            seen.add(identifier)
            rows.append(row)
    return rows
