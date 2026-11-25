"""Synthetic surface responses driven by the rock column and mineralized intervals."""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from .observation_tools import _number


CHANNELS = {
    "magnetic": ("magnetic_anomaly_nt", "magnetic_sigma_nt"),
    "gamma": ("gamma_count_rate_cps", "gamma_sigma_cps"),
}
LEGACY_MODEL = "synthetic_surface_response"
CURRENT_MODEL = "reference_ground_survey"
RADIOELEMENTS = ("potassium_percent", "uranium_ppm", "thorium_ppm")
SOURCE_FIELDS = {*RADIOELEMENTS, "magnetic_susceptibility_si", "magnetic_reference_grade_percent",
                 "gamma_response_cps", "uranium_equilibrium_factor"}
LEGACY_DEFAULTS = {
    "magnetic_decay_m": 110.0,
    "magnetic_spread_m": 40.0,
    "magnetic_reference_si": 0.003,
    "magnetic_gain_nt": 20000.0,
    "gamma_decay_m": 0.35,
    "gamma_background_cps": 8.0,
}
FIELD_DEFAULTS = {
    "geomagnetic_field_nt": 50000.0,
    "magnetic_inclination_deg": 65.0,
    "magnetic_source_radius_m": 45.0,
    "magnetic_sensor_height_m": 1.5,
    "magnetic_spread_m": 25.0,
    "gamma_mass_attenuation_cm2_g": 0.045,
    "gamma_background_cps": 1.0,
    # IAEA-TECDOC-1363, table 4.1: sum the sensitivities across the three windows.
    "gamma_sensitivity_k_cps_per_percent": 3.36,
    "gamma_sensitivity_u_cps_per_ppm": 0.586,
    "gamma_sensitivity_th_cps_per_ppm": 0.265,
    "soil_potassium_retention": 0.7,
}
GAMMA_SENSITIVITY_KEYS = ("gamma_sensitivity_k_cps_per_percent", "gamma_sensitivity_u_cps_per_ppm",
                          "gamma_sensitivity_th_cps_per_ppm")
U_PPM_PER_PERCENT_U3O8 = 8480.0
LEGACY_ONLY_SETTINGS = LEGACY_DEFAULTS.keys() - FIELD_DEFAULTS.keys()


def _model_name(settings):
    return settings.get("model", LEGACY_MODEL if LEGACY_ONLY_SETTINGS.intersection(settings) else CURRENT_MODEL)


def validate_geophysical_model(settings, rocks, minerals):
    if not isinstance(settings, dict) or not isinstance(settings.get("enabled", False), bool):
        raise ValueError("geophysics.enabled: требуется логическое значение")
    if not settings.get("enabled"):
        return
    model = _model_name(settings)
    if model not in (LEGACY_MODEL, CURRENT_MODEL):
        raise ValueError("geophysics.model: неизвестная модель измерений")
    defaults = LEGACY_DEFAULTS if model == LEGACY_MODEL else FIELD_DEFAULTS
    for name, default in defaults.items():
        value = settings.get(name, default)
        if name == "magnetic_inclination_deg":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not -90 <= value <= 90:
                raise ValueError("geophysics.magnetic_inclination_deg: требуется угол в диапазоне [−90, 90]")
        else:
            _number(value, f"geophysics.{name}", positive=name in {
                "magnetic_decay_m", "gamma_decay_m", "magnetic_gain_nt", "geomagnetic_field_nt",
                "magnetic_source_radius_m", "gamma_mass_attenuation_cm2_g"
            })
    if model == CURRENT_MODEL and settings.get("soil_potassium_retention", FIELD_DEFAULTS["soil_potassium_retention"]) > 1:
        raise ValueError("geophysics.soil_potassium_retention: требуется доля от 0 до 1")
    for definition in (*rocks, *minerals):
        entries = definition.get("geophysical_source", {})
        if not isinstance(entries, dict) or not entries.keys() <= SOURCE_FIELDS:
            raise ValueError(f"{definition['id']}.geophysical_source: неизвестные параметры источника")
        for name, value in entries.items():
            _number(value, f"{definition['id']}.geophysical_source.{name}", positive=name == "magnetic_reference_grade_percent")
            if name == "uranium_equilibrium_factor" and value > 1:
                raise ValueError(f"{definition['id']}.uranium_equilibrium_factor: требуется доля от 0 до 1")


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


def _radioelement_response(source, parameters):
    if not any(element in source for element in RADIOELEMENTS):
        return source.get("gamma_response_cps", 0)
    return sum(source.get(element, 0) * parameters[sensitivity]
               for element, sensitivity in zip(RADIOELEMENTS, GAMMA_SENSITIVITY_KEYS, strict=True))


def _depths(interval, elevation):
    top = max(0.0, interval["from_depth_m"] + elevation)
    return top, max(top, interval["to_depth_m"] + elevation)


def _ore_sources(cell, deposits, mineral_sources):
    for interval in cell.get("mineralization", ()):
        deposit = deposits[interval["deposit_id"]]
        source = mineral_sources.get(deposit.get("mineral_id"))
        if source:
            yield interval, deposit, source


def _ore_gamma_response(ore, deposit, ore_source, rock_source, model):
    if "uranium_equilibrium_factor" in ore_source and ore.get("grade_unit") == "% U₃O₈":
        uranium = ore["average_grade"] * U_PPM_PER_PERCENT_U3O8 * ore_source["uranium_equilibrium_factor"]
        return max(0, uranium - rock_source.get("uranium_ppm", 0)) * model["gamma_sensitivity_u_cps_per_ppm"]
    fraction = min(1, ore["average_grade"] / deposit["max_grade"])
    return _radioelement_response(ore_source, model) * fraction


def local_gamma_response(part, model, rock_sources, deposits, mineral_sources):
    """Synthetic response of the surrounding material in the existing survey scale."""
    source = rock_sources.get(part["rock_id"], {})
    return (model["gamma_background_cps"] + _radioelement_response(source, model)
            + sum(_ore_gamma_response(ore, deposit, ore_source, source, model)
                  for ore, deposit, ore_source in _ore_sources(part, deposits, mineral_sources)))


def _legacy_response(cell, model, rock_sources, ores):
    elevation = cell.get("surface_elevation_m", 0)
    magnetization, radiation = 0.0, model["gamma_background_cps"]
    sources = [(interval, rock_sources.get(interval["rock_id"], {}), 1.0) for interval in cell["intervals"]]
    sources.extend((interval, source, min(1, interval["average_grade"] / deposit["max_grade"]))
                   for interval, deposit, source in ores)
    for interval, source, fraction in sources:
        top, bottom = _depths(interval, elevation)
        decay = model["magnetic_decay_m"]
        magnetization += source.get("magnetic_susceptibility_si", 0) * fraction * (
            math.exp(-top / decay) - math.exp(-bottom / decay))
        decay = model["gamma_decay_m"]
        gamma_source = source.get("gamma_response_cps")
        if gamma_source is None:
            gamma_source = _radioelement_response(source, FIELD_DEFAULTS)
        radiation += gamma_source * fraction * (math.exp(-top / decay) - math.exp(-bottom / decay))
    return model["magnetic_gain_nt"] * (magnetization - model["magnetic_reference_si"]), radiation


def _magnetic_weight(top, bottom, height, radius):
    # On-axis field of a uniformly magnetized equivalent cylindrical layer.
    top, bottom = top + height, bottom + height
    return bottom / math.hypot(bottom, radius) - top / math.hypot(top, radius)


def _ground_response(cell, model, rock_sources, ores, soil_id, magnetic_scale):
    elevation = cell.get("surface_elevation_m", 0)
    height, radius = model["magnetic_sensor_height_m"], model["magnetic_source_radius_m"]
    magnetic, radiation, optical_depth = 0.0, model["gamma_background_cps"], 0.0
    intervals = cell["intervals"]
    parent = next((rock_sources.get(interval["rock_id"], {}) for interval in intervals
                   if interval["rock_id"] != soil_id), {})

    for interval in intervals:
        top, bottom = _depths(interval, elevation)
        source = rock_sources.get(interval["rock_id"], {})
        magnetic += source.get("magnetic_susceptibility_si", 0) * _magnetic_weight(top, bottom, height, radius)
        if interval["rock_id"] == soil_id and all(element in parent for element in RADIOELEMENTS):
            source = {**source, **{element: parent[element] for element in RADIOELEMENTS}}
            source["potassium_percent"] *= model["soil_potassium_retention"]
        density = interval.get("properties", {}).get("density_g_cm3", 2.2)
        attenuation = 100 * density * model["gamma_mass_attenuation_cm2_g"]
        tau_bottom = optical_depth + attenuation * (bottom - top)
        radiation += _radioelement_response(source, model) * (math.exp(-optical_depth) - math.exp(-tau_bottom))
        for ore, deposit, ore_source in ores:
            ore_top, ore_bottom = _depths(ore, elevation)
            start, end = max(top, ore_top), min(bottom, ore_bottom)
            if end <= start:
                continue
            gamma_source = _ore_gamma_response(ore, deposit, ore_source, source, model)
            tau_start = optical_depth + attenuation * (start - top)
            tau_end = optical_depth + attenuation * (end - top)
            radiation += gamma_source * (math.exp(-tau_start) - math.exp(-tau_end))
        optical_depth = tau_bottom

    for ore, deposit, source in ores:
        reference_grade = source.get("magnetic_reference_grade_percent", deposit["max_grade"])
        fraction = ore["average_grade"] / reference_grade
        top, bottom = _depths(ore, elevation)
        magnetic += source.get("magnetic_susceptibility_si", 0) * fraction * _magnetic_weight(top, bottom, height, radius)
    return magnetic_scale * magnetic, radiation


def add_geophysical_fields(truth: dict[str, Any], settings: dict[str, Any], rocks, minerals, *, replace=False) -> None:
    """Add versioned fields to a generated or previously saved map."""
    if "geophysics" in truth and not replace:
        return
    validate_geophysical_model(settings, rocks, minerals)
    if not settings.get("enabled"):
        return
    name = _model_name(settings)
    defaults = LEGACY_DEFAULTS if name == LEGACY_MODEL else FIELD_DEFAULTS
    model = {key: settings.get(key, value) for key, value in defaults.items()}
    rock_sources = {rock["id"]: rock.get("geophysical_source", {}) for rock in rocks}
    for rock in truth["rocks"]:
        rock_id = rock["id"]
        if "geophysical_source" in rock and (not replace or rock_id not in rock_sources):
            rock_sources[rock_id] = rock["geophysical_source"]
        elif rock_sources.get(rock_id):
            rock["geophysical_source"] = dict(rock_sources[rock_id])
        elif replace:
            rock.pop("geophysical_source", None)
    mineral_sources = {mineral["id"]: mineral.get("geophysical_source", {}) for mineral in minerals}
    deposits = {deposit["id"]: deposit for deposit in truth["deposits"]}
    dims = truth["dimensions"]
    width, height = dims["width_cells"], dims["height_cells"]
    cells = sorted(truth["cells"], key=lambda cell: (cell["y_index"], cell["x_index"]))
    magnetic, gamma = [], []

    if name == CURRENT_MODEL:
        soil_id = truth.get("terrain", {}).get("surface_cover_rock_id", "soil")
        inclination = math.radians(model["magnetic_inclination_deg"])
        # Project the on-axis tensor (transverse components are −1/2 of axial) onto the inducing field.
        magnetic_scale = model["geomagnetic_field_nt"] * (1.5 * math.sin(inclination)**2 - 0.5) / 2
    for cell in cells:
        ores = list(_ore_sources(cell, deposits, mineral_sources))
        if name == CURRENT_MODEL:
            anomaly, radiation = _ground_response(cell, model, rock_sources, ores, soil_id, magnetic_scale)
        else:
            anomaly, radiation = _legacy_response(cell, model, rock_sources, ores)
        magnetic.append(anomaly)
        gamma.append(radiation)

    magnetic = _smooth_magnetic(magnetic, width, height, model["magnetic_spread_m"] / dims["cell_size_m"])
    reference = median(magnetic) if name == CURRENT_MODEL else 0.0
    for cell, anomaly, radiation in zip(cells, magnetic, gamma, strict=True):
        cell["geophysical_fields"] = {"magnetic_anomaly_nt": round(anomaly - reference, 4), "gamma_count_rate_cps": round(radiation, 4)}
    truth["geophysics"] = {
        "model": name,
        "parameters": model,
        "mineral_sources": {key: dict(source) for key, source in mineral_sources.items() if source},
        "ranges": {field: [min(cell["geophysical_fields"][field] for cell in cells),
                           max(cell["geophysical_fields"][field] for cell in cells)] for field, _ in CHANNELS.values()},
    }
    if name == CURRENT_MODEL:
        truth["geophysics"]["magnetic_reference_response_nt"] = round(reference, 4)
    truth["schema_version"] = "2.2"
