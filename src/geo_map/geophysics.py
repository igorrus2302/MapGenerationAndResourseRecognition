"""Synthetic surface responses driven by the rock column and mineralized intervals."""

from __future__ import annotations

import math
from typing import Any

from .observation_tools import _number


CHANNELS = {
    "magnetic": ("magnetic_anomaly_nt", "magnetic_sigma_nt"),
    "gamma": ("gamma_count_rate_cps", "gamma_sigma_cps"),
}
SOURCE_FIELDS = {"magnetic_susceptibility_si", "gamma_response_cps"}
FIELD_DEFAULTS = {
    "magnetic_decay_m": 110.0,
    "magnetic_spread_m": 40.0,
    "magnetic_reference_si": 0.003,
    "magnetic_gain_nt": 20000.0,
    "gamma_decay_m": 0.35,
    "gamma_background_cps": 8.0,
}


def validate_geophysical_model(settings, rocks, minerals):
    if not isinstance(settings, dict) or not isinstance(settings.get("enabled", False), bool):
        raise ValueError("geophysics.enabled: требуется логическое значение")
    if not settings.get("enabled"):
        return
    for name, default in FIELD_DEFAULTS.items():
        value = settings.get(name, default)
        _number(value, f"geophysics.{name}", positive=name.endswith("_m") or name == "magnetic_gain_nt")
    for definition in (*rocks, *minerals):
        entries = definition.get("geophysical_source", {})
        if not isinstance(entries, dict) or not entries.keys() <= SOURCE_FIELDS:
            raise ValueError(f"{definition['id']}.geophysical_source: неизвестные параметры источника")
        for name, value in entries.items():
            _number(value, f"{definition['id']}.geophysical_source.{name}")


def _smooth_magnetic(values, width, height, sigma_cells):
    # Separable Gaussian with edge normalization. Shorter domains need no larger kernel.
    if sigma_cells == 0:
        return values
    radius = math.ceil(min(max(width, height) - 1, 3 * sigma_cells))
    weights = [math.exp(-0.5 * distance * distance) for distance in (offset / sigma_cells for offset in range(radius + 1))]
    for axis_size, stride in ((width, 1), (height, width)):
        neighborhoods = []
        for coordinate in range(axis_size):
            neighborhood = [(offset * stride, weights[abs(offset)]) for offset in
                            range(max(-radius, -coordinate), min(radius, axis_size - 1 - coordinate) + 1)]
            total = sum(weight for _, weight in neighborhood)
            neighborhoods.append([(shift, weight / total) for shift, weight in neighborhood])
        values = [sum(values[index + shift] * weight for shift, weight in neighborhoods[index // stride % axis_size])
                  for index in range(len(values))]
    return values


def add_geophysical_fields(truth: dict[str, Any], settings: dict[str, Any], rocks, minerals) -> None:
    """Add versioned fields to a generated or previously saved map."""
    if "geophysics" in truth:
        return
    validate_geophysical_model(settings, rocks, minerals)
    if not settings.get("enabled"):
        return
    model = {**FIELD_DEFAULTS, **settings}
    rock_sources = {rock["id"]: rock.get("geophysical_source", {}) for rock in rocks}
    for rock in truth["rocks"]:
        rock_id = rock["id"]
        if "geophysical_source" in rock:
            rock_sources[rock_id] = rock["geophysical_source"]
        elif rock_sources.get(rock_id):
            rock["geophysical_source"] = dict(rock_sources[rock_id])
    mineral_sources = {mineral["id"]: mineral.get("geophysical_source", {}) for mineral in minerals}
    deposits = {deposit["id"]: deposit for deposit in truth["deposits"]}
    dims = truth["dimensions"]
    width, height = dims["width_cells"], dims["height_cells"]
    cells = sorted(truth["cells"], key=lambda cell: (cell["y_index"], cell["x_index"]))
    magnetic, gamma = [], []

    for cell in cells:
        elevation = cell.get("surface_elevation_m", 0)
        magnetization, radiation = 0.0, model["gamma_background_cps"]
        sources = [(interval, rock_sources.get(interval["rock_id"], {}), 1.0) for interval in cell["intervals"]]
        for interval in cell.get("mineralization", ()):
            deposit = deposits[interval["deposit_id"]]
            source = mineral_sources.get(deposit["mineral_id"], {})
            if source:
                grade_fraction = min(1, interval["average_grade"] / deposit["max_grade"])
                sources.append((interval, source, grade_fraction))
        for interval, source, fraction in sources:
            top = max(0.0, interval["from_depth_m"] + elevation)
            bottom = max(top, interval["to_depth_m"] + elevation)
            susceptibility = source.get("magnetic_susceptibility_si", 0)
            if susceptibility:
                decay = model["magnetic_decay_m"]
                magnetization += susceptibility * fraction * (math.exp(-top / decay) - math.exp(-bottom / decay))
            gamma_source = source.get("gamma_response_cps", 0)
            if gamma_source:
                decay = model["gamma_decay_m"]
                radiation += gamma_source * fraction * (math.exp(-top / decay) - math.exp(-bottom / decay))
        magnetic.append(model["magnetic_gain_nt"] * (magnetization - model["magnetic_reference_si"]))
        gamma.append(radiation)

    magnetic = _smooth_magnetic(magnetic, width, height, model["magnetic_spread_m"] / dims["cell_size_m"])
    for cell, anomaly, radiation in zip(cells, magnetic, gamma, strict=True):
        cell["geophysical_fields"] = {"magnetic_anomaly_nt": round(anomaly, 4), "gamma_count_rate_cps": round(radiation, 4)}
    truth["geophysics"] = {
        "model": "synthetic_surface_response",
        "parameters": {name: model[name] for name in FIELD_DEFAULTS},
        "ranges": {field: [min(cell["geophysical_fields"][field] for cell in cells),
                           max(cell["geophysical_fields"][field] for cell in cells)] for field, _ in CHANNELS.values()},
    }
    truth["schema_version"] = "2.2"
