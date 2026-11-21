"""Synthetic field surveys, trench sampling, fault observations and laboratory controls."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Callable

from .boreholes import direction as borehole_direction
from .generator import _fault_signed_distance_m
from .geophysics import CHANNELS
from .observation_tools import TruthSampler, _number, _rng, measure_grade, surface_grid_shape


EXTRA_TABLE_FIELDS = {
    "surface_geochemistry": "campaign_id sample_id x_m y_m sample_date sample_material sampling_depth_from_m sampling_depth_to_m sampling_method analyte result_value result_qualifier unit detection_limit analysis_method laboratory certificate_id position_uncertainty_m qc_type parent_sample_id qc_flag notes".split(),
    "outcrop_observations": "campaign_id observation_id x_m y_m surface_elevation_m observed_rock_id observed_rock_name observation_method position_uncertainty_m survey_date".split(),
    "terrain_observations": "campaign_id observation_id x_m y_m surface_elevation_m elevation_uncertainty_m slope_deg local_relief_m terrain_type observation_method survey_date".split(),
    "geophysical_observations": "campaign_id observation_id x_m y_m surface_elevation_m magnetic_anomaly_nt magnetic_sigma_nt gamma_count_rate_cps gamma_sigma_cps position_uncertainty_m observation_method survey_date".split(),
    "trenches": "campaign_id trench_id start_x_m start_y_m end_x_m end_y_m depth_m width_m surveyed_length_m position_uncertainty_m trench_status survey_date".split(),
    "trench_intervals": "campaign_id trench_id interval_id from_m to_m observed_rock_id observed_rock_name sample_material description confidence".split(),
    "trench_samples": "campaign_id trench_id sample_id from_m to_m sampling_depth_from_m sampling_depth_to_m sample_material sampling_method analyte result_value result_qualifier unit detection_limit analysis_method laboratory certificate_id qc_type qc_flag".split(),
    "fault_intersections": "campaign_id observation_id hole_id from_m to_m observation_method confidence description".split(),
    "quality_control": "campaign_id control_id sample_id parent_sample_id sample_source hole_id trench_id qc_type analyte result_value result_qualifier unit detection_limit reference_value reference_uncertainty absolute_difference relative_difference_percent acceptance_limit acceptance_unit qc_flag notes".split(),
}

SURFACE_ANALYTES = {"Cu", "Fe", "Au", "Mn", "Al₂O₃", "U₃O₈", "Cr₂O₃", "Li₂O", "P₂O₅"}
MAX_ANALYSES = 1000000
TERRAIN_SURVEY_DEFAULTS = {"elevation_sigma_m": 0.0, "slope_threshold_deg": 7, "local_relief_threshold_m": 3}


def _enabled(config: dict[str, Any], name: str) -> bool:
    return config.get(name, {}).get("enabled", name == "structures" and name not in config)


def _count(value: Any, name: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not (0 if allow_zero else 1) <= value <= 10000:
        raise ValueError(f"{name}: требуется целое число от {0 if allow_zero else 1} до 10000")
    return value


def _coordinate(value: Any, name: str, limit: float, *, endpoint: bool = False) -> float:
    number = _number(value, name)
    if number > limit or (number == limit and not endpoint):
        raise ValueError(f"{name}: точка находится вне карты")
    return number


def validate_extensions(config: dict[str, Any], dimensions: dict[str, Any], planned_samples: int = 0,
                        planned_analyses: int = 0) -> None:
    for name in ("structures", "surface_geochemistry", "trenches", "quality_control", "outcrops", "terrain_survey", "geophysical_survey"):
        settings = config.get(name, {})
        if not isinstance(settings, dict) or not isinstance(settings.get("enabled", False), bool):
            raise ValueError(f"{name}: нужен объект с логическим enabled")
    structures = config.get("structures", {})
    for key in ("observe_contacts", "observe_faults"):
        if not isinstance(structures.get(key, True), bool):
            raise ValueError(f"structures.{key}: требуется логическое значение")
    if structures.get("method", "core_logging") not in {"core_logging", "oriented_core"}:
        raise ValueError("structures.method: допустимы core_logging и oriented_core")
    for key in ("orientation_sigma_deg", "depth_sigma_m"):
        _number(structures.get(key, 0), f"structures.{key}")
    if _number(structures.get("fault_detection_probability", 1), "fault_detection_probability") > 1:
        raise ValueError("Вероятность обнаружения разлома должна лежать в [0, 1]")

    total_analyses = planned_analyses
    if _enabled(config, "outcrops"):
        settings = config["outcrops"]
        if _count(settings["point_count"], "outcrops.point_count") > MAX_ANALYSES:
            raise ValueError("outcrops.point_count превышает миллион точек")
        _number(settings.get("position_sigma_m", 0), "outcrops.position_sigma_m")
    if _enabled(config, "terrain_survey"):
        settings = config["terrain_survey"]
        _count(settings.get("point_count"), "terrain_survey.point_count")
        for name, default in TERRAIN_SURVEY_DEFAULTS.items():
            value = _number(settings.get(name, default), f"terrain_survey.{name}", positive=name != "elevation_sigma_m")
            if name == "slope_threshold_deg" and value >= 90:
                raise ValueError("terrain_survey.slope_threshold_deg: угол должен быть меньше 90°")
    if _enabled(config, "geophysical_survey"):
        settings = config["geophysical_survey"]
        _count(settings.get("point_count"), "geophysical_survey.point_count")
        for name in ("position_sigma_m", *(sigma for _, sigma in CHANNELS.values())):
            _number(settings.get(name, 0), f"geophysical_survey.{name}")
    if _enabled(config, "surface_geochemistry"):
        surface = config["surface_geochemistry"]
        if surface.get("layout", "grid") not in {"grid", "random", "manual"}:
            raise ValueError("surface_geochemistry.layout: допустимы grid, random, manual")
        if surface.get("layout") == "manual":
            points = surface.get("points", [])
            if not points:
                raise ValueError("Для ручной геохимической съёмки нужны points")
            identifiers = set()
            for index, point in enumerate(points):
                identifier = point.get("sample_id", f"SG-{index + 1:03d}")
                if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers:
                    raise ValueError("sample_id поверхностной пробы должен быть непустым и уникальным")
                identifiers.add(identifier)
                _coordinate(point["x_m"], "x_m", dimensions["width_m"])
                _coordinate(point["y_m"], "y_m", dimensions["height_m"])
            point_count = len(points)
        else:
            point_count = _count(surface["point_count"], "surface_geochemistry.point_count")
        top = _number(surface["sampling_depth_from_m"], "sampling_depth_from_m")
        bottom = _number(surface["sampling_depth_to_m"], "sampling_depth_to_m", positive=True)
        if not top < bottom <= dimensions["depth_m"]:
            raise ValueError("Недопустимая глубина почвенного опробования")
        if surface.get("sample_material", "soil") != "soil":
            raise ValueError("Поверхностная геохимия поддерживает только материал soil")
        _number(surface.get("position_sigma_m", 0), "surface.position_sigma_m")
        analytes = surface.get("analytes", [])
        names = [item["analyte"] for item in analytes]
        if not names or len(names) != len(set(names)):
            raise ValueError("Для поверхностной геохимии нужен список уникальных аналитов")
        for item in analytes:
            if item["analyte"] not in SURFACE_ANALYTES:
                raise ValueError(f"Нет почвенной модели для {item['analyte']}")
            if not isinstance(item.get("unit"), str) or not item["unit"].strip():
                raise ValueError("Для поверхностного аналита нужна единица")
            for key in ("detection_limit", "depth_decay_m", "lateral_spread_m", "background_scale_m"):
                _number(item[key], f"surface.{key}", positive=True)
            for key in ("background_grade", "response_factor", "background_variation_fraction"):
                _number(item[key], f"surface.{key}")
            if item["background_variation_fraction"] > 1:
                raise ValueError("background_variation_fraction должна лежать в [0, 1]")
            if item["lateral_spread_m"] < dimensions["cell_size_m"] / 2:
                raise ValueError("Радиус рассеивания не может быть меньше половины исходной ячейки")
        total_analyses += point_count * len(analytes)
        planned_samples += point_count

    if _enabled(config, "trenches"):
        trench = config["trenches"]
        depth = _number(trench["depth_m"], "trenches.depth_m", positive=True)
        if depth > dimensions["depth_m"]:
            raise ValueError("Траншея глубже истинной карты")
        for key in ("width_m", "sample_length_m", "sampling_height_m"):
            _number(trench[key], f"trenches.{key}", positive=True)
        if trench["sample_length_m"] < 0.000001 or trench["sampling_height_m"] > depth:
            raise ValueError("Недопустимый интервал или высота траншейной пробы")
        _number(trench.get("position_sigma_m", 0), "trenches.position_sigma_m")
        paths = _trench_paths(dimensions, trench)
        identifiers = set()
        for path in paths:
            if not isinstance(path["trench_id"], str) or not path["trench_id"].strip() or path["trench_id"] in identifiers:
                raise ValueError("trench_id должен быть непустым и уникальным")
            identifiers.add(path["trench_id"])
            for prefix in ("start", "end"):
                for axis, limit in (("x", "width_m"), ("y", "height_m")):
                    _coordinate(path[f"{prefix}_{axis}_m"], f"{prefix}_{axis}_m", dimensions[limit], endpoint=True)
            length = _path_length(path)
            if length <= 0:
                raise ValueError("Длина траншеи должна быть положительной")
            count = math.ceil(length / trench["sample_length_m"])
            total_analyses += count * len(config["analytes"])
            planned_samples += count

    qc = config.get("quality_control", {})
    bias = qc.get("batch_bias_fraction", 0)
    if isinstance(bias, bool) or not isinstance(bias, (float, int)) or not math.isfinite(bias) or not -1 < bias <= 10:
        raise ValueError("batch_bias_fraction должна лежать в (-1, 10]")
    for key in ("contamination_detection_limits", "duplicate_preparation_sigma"):
        _number(qc.get(key, 0), f"quality_control.{key}")
    if _enabled(config, "quality_control"):
        for key in ("duplicate_every", "blank_every", "standard_every"):
            _count(qc.get(key, 0), f"quality_control.{key}", allow_zero=True)
        for key in ("duplicate_tolerance_percent", "standard_tolerance_percent", "blank_detection_limit_multiple", "standard_detection_limit_multiple"):
            _number(qc[key], f"quality_control.{key}", positive=True)
        if qc["standard_detection_limit_multiple"] <= 1:
            raise ValueError("Содержание стандарта должно превышать предел обнаружения")
        if _number(qc.get("standard_uncertainty_fraction", .01), "standard_uncertainty_fraction") > 1:
            raise ValueError("standard_uncertainty_fraction должна лежать в [0, 1]")
        largest_panel = max(len(config["analytes"]), len(config.get("surface_geochemistry", {}).get("analytes", [])))
        total_analyses += sum(math.ceil(planned_samples / qc[key]) * largest_panel for key in ("duplicate_every", "blank_every", "standard_every") if qc.get(key, 0))
    if total_analyses > MAX_ANALYSES:
        raise ValueError("План кампании вместе с QA/QC превышает миллион анализов")


def _surface_points(dimensions: dict[str, Any], config: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    if config.get("layout") == "manual":
        return [{"sample_id": f"SG-{index + 1:03d}", **point} for index, point in enumerate(config["points"])]
    count = config["point_count"]
    width, height = dimensions["width_m"], dimensions["height_m"]
    columns, rows = surface_grid_shape(dimensions, count)
    points = []
    for index in range(count):
        rng = _rng(seed, "surface-plan", index)
        x = ((index % columns) + .5) * width / columns
        y = ((index // columns) + .5) * height / rows
        if config.get("layout") == "random":
            x, y = rng.uniform(.05, .95) * width, rng.uniform(.05, .95) * height
        points.append({"sample_id": f"SG-{index + 1:03d}", "x_m": x, "y_m": y})
    return points


class SurfaceModel:
    """A depth-decaying, laterally smoothed proxy; not a transport solver."""

    def __init__(self, truth: dict[str, Any], analytes: list[dict[str, Any]]):
        self.dimensions = truth["dimensions"]
        # Run timestamps, identifiers and record order do not define a new world.
        scene_cells = []
        for cell in sorted(truth["cells"], key=lambda item: (item["y_index"], item["x_index"])):
            scene_cells.append({"x": cell["x_index"], "y": cell["y_index"],
                                "rocks": [{key: item[key] for key in ("from_depth_m", "to_depth_m", "rock_id", "properties")} for item in cell["intervals"]],
                                "minerals": [{key: item[key] for key in ("from_depth_m", "to_depth_m", "mineral", "average_grade", "grade_unit")} for item in cell["mineralization"]]})
        scene = json.dumps({"dimensions": self.dimensions, "cells": scene_cells}, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self.scene_key = int.from_bytes(hashlib.sha256(scene.encode()).digest()[:8], "big")
        self.signals = {}
        for analyte in analytes:
            signal = {}
            decay = analyte["depth_decay_m"]
            for cell in truth["cells"]:
                value = 0.0
                for interval in cell["mineralization"]:
                    if interval["mineral"] != analyte["analyte"]:
                        continue
                    if interval["grade_unit"] != analyte["unit"]:
                        raise ValueError(f"Несовместимые единицы поверхностного аналита {analyte['analyte']}")
                    elevation = cell.get("surface_elevation_m", 0)
                    top, bottom = interval["from_depth_m"] + elevation, interval["to_depth_m"] + elevation
                    value += interval["average_grade"] * (math.exp(-top / decay) - math.exp(-bottom / decay))
                signal[cell["x_index"], cell["y_index"]] = value
            self.signals[analyte["analyte"]] = signal

    def grade(self, x: float, y: float, analyte: dict[str, Any]) -> float:
        dims = self.dimensions
        step, spread = dims["cell_size_m"], analyte["lateral_spread_m"]
        weighted = total = 0.0
        x_low = max(0, math.floor((x - 3 * spread) / step))
        x_high = min(dims["width_cells"] - 1, math.floor((x + 3 * spread) / step))
        y_low = max(0, math.floor((y - 3 * spread) / step))
        y_high = min(dims["height_cells"] - 1, math.floor((y + 3 * spread) / step))
        # Include the containing column even when spread is below half a cell.
        x_low, x_high = min(x_low, math.floor(x / step)), max(x_high, math.floor(x / step))
        y_low, y_high = min(y_low, math.floor(y / step)), max(y_high, math.floor(y / step))
        for iy in range(y_low, y_high + 1):
            for ix in range(x_low, x_high + 1):
                distance2 = ((ix + .5) * step - x) ** 2 + ((iy + .5) * step - y) ** 2
                weight = math.exp(-min(700, distance2 / (2 * spread * spread)))
                weighted += weight * self.signals[analyte["analyte"]][ix, iy]
                total += weight
        scale = analyte["background_scale_m"]
        gx, gy = math.floor(x / scale), math.floor(y / scale)
        tx, ty = x / scale - gx, y / scale - gy
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        def field(ix: int, iy: int) -> float:
            return _rng(self.scene_key, "surface-background", analyte["analyte"], ix, iy).uniform(-1, 1)
        background_noise = ((1 - tx) * field(gx, gy) + tx * field(gx + 1, gy)) * (1 - ty) + ((1 - tx) * field(gx, gy + 1) + tx * field(gx + 1, gy + 1)) * ty
        background = analyte["background_grade"] * (1 + analyte["background_variation_fraction"] * background_noise)
        return background + analyte["response_factor"] * weighted / total


def _path_length(path: dict[str, Any]) -> float:
    return math.hypot(path["end_x_m"] - path["start_x_m"], path["end_y_m"] - path["start_y_m"])


def _trench_paths(dimensions: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    layout = config.get("layout", "grid")
    if layout == "manual":
        if not config.get("paths"):
            raise ValueError("Для ручного плана траншей нужны paths")
        return config["paths"]
    if layout != "grid":
        raise ValueError("trenches.layout: допустимы grid, manual")
    count = _count(config["trench_count"], "trenches.trench_count")
    length = _number(config["length_m"], "trenches.length_m", positive=True)
    angle = _number(config.get("azimuth_deg", 90), "trenches.azimuth_deg")
    if angle >= 360:
        raise ValueError("Азимут траншей должен лежать в [0, 360)")
    dx, dy = length / 2 * math.sin(math.radians(angle)), length / 2 * math.cos(math.radians(angle))
    result = []
    for index in range(count):
        cx, cy = dimensions["width_m"] / 2, (index + .5) * dimensions["height_m"] / count
        result.append({"trench_id": f"TR-{index + 1:03d}", "start_x_m": cx - dx, "start_y_m": cy - dy,
                       "end_x_m": cx + dx, "end_y_m": cy + dy})
    return result


def _path_parts(path: dict[str, Any], start: float, end: float, step: float) -> list[tuple[float, float, float, float]]:
    length = _path_length(path)
    cuts = {start, end}
    for axis in ("x", "y"):
        origin, finish = path[f"start_{axis}_m"], path[f"end_{axis}_m"]
        if abs(finish - origin) < 1e-12:
            continue
        low, high = sorted((origin, finish))
        for index in range(math.floor(low / step) + 1, math.ceil(high / step)):
            station = (index * step - origin) / (finish - origin) * length
            if start < station < end:
                cuts.add(station)
    result = []
    edges = sorted(cuts)
    for left, right in zip(edges, edges[1:]):
        fraction = (left + right) / 2 / length
        result.append((left, right,
                       path["start_x_m"] + fraction * (path["end_x_m"] - path["start_x_m"]),
                       path["start_y_m"] + fraction * (path["end_y_m"] - path["start_y_m"])))
    return result


def _laboratory_result(value: float, analyte: dict[str, Any], config: dict[str, Any], seed: int, sample_id: str) -> dict[str, Any]:
    qc = config.get("quality_control", {})
    return measure_grade(value, analyte, config.get("noise", {}), seed, sample_id, ideal=config.get("ideal", False),
                         bias_fraction=qc.get("batch_bias_fraction", 0), contamination_limits=qc.get("contamination_detection_limits", 0))


def _surface_observations(truth: dict[str, Any], config: dict[str, Any], seed: int,
                          sources: dict[str, Any], append: Callable) -> int:
    settings = config["surface_geochemistry"]
    sampler, model = TruthSampler(truth), SurfaceModel(truth, settings["analytes"])
    top, bottom = settings["sampling_depth_from_m"], settings["sampling_depth_to_m"]
    sigma = 0 if config.get("ideal") else settings.get("position_sigma_m", 0)
    unavailable = 0
    for point in _surface_points(truth["dimensions"], settings, seed):
        sample_id, x, y = point["sample_id"], point["x_m"], point["y_m"]
        if sample_id in sources:
            raise ValueError(f"Повторяется идентификатор пробы {sample_id}")
        column = sampler.column(x, y)
        elevation = column.get("surface_elevation_m", 0)
        intervals = [item for item in column["intervals"]
                     if item["from_depth_m"] < bottom - elevation and item["to_depth_m"] > top - elevation]
        if not intervals or intervals[-1]["to_depth_m"] < bottom - elevation or any(item["rock_id"] != "soil" for item in intervals):
            if truth.get("terrain"):
                unavailable += 1
                continue
            raise ValueError(f"{sample_id}: интервал почвенной пробы должен находиться в soil")
        rng = _rng(seed, "surface-position", sample_id)
        observed_x, observed_y = round(x + rng.gauss(0, sigma), 6), round(y + rng.gauss(0, sigma), 6)
        grades = {analyte["analyte"]: model.grade(x, y, analyte) for analyte in settings["analytes"]}
        sources[sample_id] = {"source": "surface", "grades": grades, "analytes": settings["analytes"]}
        for analyte in settings["analytes"]:
            append("surface_geochemistry", sample_id=sample_id, x_m=observed_x, y_m=observed_y, sample_date=config["date"],
                   sample_material="soil", sampling_depth_from_m=top, sampling_depth_to_m=bottom,
                   sampling_method="grid_soil_sample" if settings.get("layout", "grid") == "grid" else "soil_sample",
                   analyte=analyte["analyte"], **_laboratory_result(grades[analyte["analyte"]], analyte, config, seed, sample_id),
                   analysis_method="synthetic_assay", laboratory="SYNTHETIC-LAB", certificate_id=f"{config['campaign_id']}-CERT",
                   position_uncertainty_m=sigma, qc_type="primary", qc_flag="not_checked")
    return unavailable


def prepare_preliminary_survey(truth: dict[str, Any], config: dict[str, Any], seed: int) -> dict[str, Any]:
    """Prepare sampling coordinates and instrument errors for the same survey on both runtimes."""
    dimensions = truth["dimensions"]
    ideal = config.get("ideal", False)
    methods = {}
    if _enabled(config, "geophysical_survey") and "geophysics" in truth:
        settings = config["geophysical_survey"]
        position_sigma = 0 if ideal else settings.get("position_sigma_m", 0)
        uncertainties = {sigma: 0 if ideal else settings.get(sigma, 0) for _, sigma in CHANNELS.values()}
        points = _survey_positions(dimensions, {"point_count": settings["point_count"]}, seed, "GEO",
                                   "geophysics-position", position_sigma)
        for point in points:
            point["field_errors"] = {
                field: _rng(seed, "geophysics", point["observation_id"], method).gauss(0, uncertainties[sigma])
                for method, (field, sigma) in CHANNELS.items()
            }
        methods["geophysical_survey"] = {"points": points, "position_uncertainty_m": position_sigma, **uncertainties}
    if _enabled(config, "terrain_survey"):
        settings = {**TERRAIN_SURVEY_DEFAULTS, **config["terrain_survey"]}
        count = settings["point_count"]
        columns, rows = surface_grid_shape(dimensions, count)
        sigma = 0 if ideal else settings["elevation_sigma_m"]
        points = _survey_positions(dimensions, {"point_count": count}, seed, "TER", "terrain-position", 0)
        for point in points:
            point["elevation_error_m"] = _rng(seed, "terrain-elevation", point["observation_id"]).gauss(0, sigma) if sigma else 0
        methods["terrain_survey"] = {
            "points": points, "columns": columns, "rows": rows, "elevation_uncertainty_m": sigma,
            "slope_threshold_deg": settings["slope_threshold_deg"],
            "local_relief_threshold_m": settings["local_relief_threshold_m"],
        }
    if _enabled(config, "outcrops"):
        settings = config["outcrops"]
        sigma = 0 if ideal else settings.get("position_sigma_m", 0)
        points = _survey_positions(dimensions, settings, seed, "OUT", "outcrop-position", sigma)
        methods["outcrops"] = {"points": points, "position_uncertainty_m": sigma}
    return {"campaign_id": config["campaign_id"], "date": config["date"], "methods": methods}


def _survey_positions(dimensions, settings, seed, prefix, error_key, sigma):
    points = []
    for index, point in enumerate(_surface_points(dimensions, settings, seed), 1):
        identifier = f"{prefix}-{index:04d}"
        x, y = point["x_m"], point["y_m"]
        rng = _rng(seed, error_key, identifier) if sigma else None
        offset_x, offset_y = (rng.gauss(0, sigma), rng.gauss(0, sigma)) if rng else (0, 0)
        points.append({"observation_id": identifier, "position": [x, y],
                       "x_m": round(x + offset_x, 6), "y_m": round(y + offset_y, 6)})
    return points


def _outcrop_observations(truth: dict[str, Any], plan: dict[str, Any], sampler: TruthSampler, append: Callable) -> None:
    settings = plan["methods"]["outcrops"]
    names = {rock["id"]: rock["name"] for rock in truth["rocks"]}
    cover = truth.get("terrain", {}).get("surface_cover_rock_id", "soil")
    for point in settings["points"]:
        cell = sampler.column(*point["position"])
        rock = cell["intervals"][0]["rock_id"]
        if rock == cover:
            continue
        append("outcrop_observations", observation_id=point["observation_id"], x_m=point["x_m"], y_m=point["y_m"],
               surface_elevation_m=cell.get("surface_elevation_m", 0),
               observed_rock_id=rock, observed_rock_name=names[rock], observation_method="surface_mapping",
               position_uncertainty_m=settings["position_uncertainty_m"], survey_date=plan["date"])


def _terrain_morphology(elevations: dict[tuple[int, int], float], column: int, row: int,
                       dx_m: float, dy_m: float) -> tuple[float | None, float | None]:
    """Use survey points on both axes where available, with one-sided slopes at edges."""
    center = elevations[column, row]
    gradients, reference_heights = [], []
    for dx, dy, spacing in ((1, 0, dx_m), (0, 1, dy_m)):
        before = elevations.get((column - dx, row - dy))
        after = elevations.get((column + dx, row + dy))
        if before is None and after is None:
            continue
        if before is None:
            gradients.append((after - center) / spacing)
        elif after is None:
            gradients.append((center - before) / spacing)
        else:
            gradients.append((after - before) / (2 * spacing))
            farther_before = elevations.get((column - 2 * dx, row - 2 * dy))
            farther_after = elevations.get((column + 2 * dx, row + 2 * dy))
            if farther_before is not None and farther_after is not None:
                before, after = farther_before, farther_after
            reference_heights.append((before + after) / 2)
    slope = round(math.degrees(math.atan(math.hypot(*gradients))), 3) if gradients else None
    local_relief = round(center - sum(reference_heights) / len(reference_heights), 3) if reference_heights else None
    return slope, local_relief


def _terrain_observations(plan: dict[str, Any], sampler: TruthSampler, append: Callable) -> None:
    settings = plan["methods"]["terrain_survey"]
    dimensions = sampler.dimensions
    columns = settings["columns"]
    dx_m, dy_m = dimensions["width_m"] / columns, dimensions["height_m"] / settings["rows"]
    points = settings["points"]
    elevations = {}
    for index, point in enumerate(points):
        elevation = sampler.column(*point["position"]).get("surface_elevation_m", 0)
        elevations[index % columns, index // columns] = round(elevation + point["elevation_error_m"], 3)
    for index, point in enumerate(points):
        grid_index = index % columns, index // columns
        slope, local_relief = _terrain_morphology(elevations, *grid_index, dx_m, dy_m)
        terrain_type = "flat"
        if slope is None:
            terrain_type = "undetermined"
        elif slope >= settings["slope_threshold_deg"]:
            terrain_type = "slope"
        elif local_relief is not None:
            threshold = settings["local_relief_threshold_m"]
            if local_relief >= threshold:
                terrain_type = "hill"
            elif local_relief <= -threshold:
                terrain_type = "depression"
        append("terrain_observations", observation_id=point["observation_id"], x_m=point["x_m"], y_m=point["y_m"],
               surface_elevation_m=elevations[grid_index], elevation_uncertainty_m=settings["elevation_uncertainty_m"],
               slope_deg=slope, local_relief_m=local_relief, terrain_type=terrain_type,
               observation_method="grid_elevation_survey", survey_date=plan["date"])


def _geophysical_observations(plan: dict[str, Any], sampler: TruthSampler, append: Callable) -> None:
    settings = plan["methods"]["geophysical_survey"]
    for point in settings["points"]:
        cell = sampler.column(*point["position"])
        measurements = {}
        for method, (field, sigma) in CHANNELS.items():
            measured = cell["geophysical_fields"][field] + point["field_errors"][field]
            measurements[field] = round(max(0, measured) if method == "gamma" else measured, 4)
            measurements[sigma] = settings[sigma]
        append("geophysical_observations", observation_id=point["observation_id"], x_m=point["x_m"], y_m=point["y_m"],
               surface_elevation_m=cell.get("surface_elevation_m", 0), **measurements,
               position_uncertainty_m=settings["position_uncertainty_m"],
               observation_method="ground_geophysical_survey", survey_date=plan["date"])


def survey_preliminary(truth: dict[str, Any], config: dict[str, Any], seed: int,
                       sampler: TruthSampler, append: Callable) -> None:
    """Collect surface survey records before planning the field expedition."""
    plan = prepare_preliminary_survey(truth, config, seed)
    if "geophysical_survey" in plan["methods"]:
        _geophysical_observations(plan, sampler, append)
    if "terrain_survey" in plan["methods"]:
        _terrain_observations(plan, sampler, append)
    if "outcrops" in plan["methods"]:
        _outcrop_observations(truth, plan, sampler, append)


def _trench_observations(truth: dict[str, Any], config: dict[str, Any], seed: int,
                         sources: dict[str, Any], append: Callable) -> int:
    settings, sampler = config["trenches"], TruthSampler(truth)
    rocks = {rock["id"]: rock for rock in truth["rocks"]}
    depth, height = settings["depth_m"], settings["sampling_height_m"]
    sigma = 0 if config.get("ideal") else settings.get("position_sigma_m", 0)
    missing = 0
    for path in _trench_paths(truth["dimensions"], settings):
        identifier, length = path["trench_id"], _path_length(path)
        rng = _rng(seed, "trench-position", identifier)
        dx, dy = rng.gauss(0, sigma), rng.gauss(0, sigma)
        append("trenches", trench_id=identifier, start_x_m=round(path["start_x_m"] + dx, 6),
               start_y_m=round(path["start_y_m"] + dy, 6), end_x_m=round(path["end_x_m"] + dx, 6),
               end_y_m=round(path["end_y_m"] + dy, 6), depth_m=depth, width_m=settings["width_m"],
               surveyed_length_m=length, position_uncertainty_m=sigma, trench_status="completed", survey_date=config["date"])
        logs = []
        for left, right, x, y in _path_parts(path, 0, length, truth["dimensions"]["cell_size_m"]):
            floor = depth - min(1e-7, depth / 2)
            rock_id = sampler.segments(x, y, floor, depth)[-1]["rock_id"]
            if logs and logs[-1][2] == rock_id:
                logs[-1] = (logs[-1][0], right, rock_id)
            else:
                logs.append((left, right, rock_id))
        for index, (left, right, rock_id) in enumerate(logs):
            rock = rocks[rock_id]
            append("trench_intervals", trench_id=identifier, interval_id=f"{identifier}-L{index + 1:03d}",
                   from_m=left, to_m=right, observed_rock_id=rock_id, observed_rock_name=rock["name"],
                   sample_material="soil" if rock_id == "soil" else "rock", description=f"Описание дна: {rock['name']}",
                   confidence="high" if config.get("ideal") else "medium")
        step = settings["sample_length_m"]
        for index in range(math.ceil(length / step)):
            start = round(index * step, 6)
            if start >= length:
                break
            end = min(length, round((index + 1) * step, 6))
            sample_id = f"{identifier}-S{index + 1:04d}"
            if sample_id in sources:
                raise ValueError(f"Повторяется идентификатор пробы {sample_id}")
            if not config.get("ideal") and _rng(seed, "sample", sample_id).random() < config.get("noise", {}).get("missing_sample_probability", 0):
                missing += 1
                continue
            mass, weighted = 0.0, {item["analyte"]: 0.0 for item in config["analytes"]}
            materials = set()
            for left, right, x, y in _path_parts(path, start, end, truth["dimensions"]["cell_size_m"]):
                sample = sampler.sample(x, y, depth - height, depth, config["analytes"])
                part_mass = (right - left) * height * sample["density_g_cm3"]
                mass += part_mass
                for name, value in sample["grades"].items():
                    weighted[name] += value * part_mass
                for part in sampler.segments(x, y, depth - height, depth):
                    materials.add("soil" if part["rock_id"] == "soil" else "rock")
            grades = {name: value / mass for name, value in weighted.items()}
            sources[sample_id] = {"source": "trench", "trench_id": identifier, "grades": grades, "analytes": config["analytes"]}
            for analyte in config["analytes"]:
                append("trench_samples", trench_id=identifier, sample_id=sample_id, from_m=start, to_m=end,
                       sampling_depth_from_m=depth - height, sampling_depth_to_m=depth,
                       sample_material=next(iter(materials)) if len(materials) == 1 else "regolith", sampling_method="channel",
                       analyte=analyte["analyte"], **_laboratory_result(grades[analyte["analyte"]], analyte, config, seed, sample_id),
                       analysis_method="synthetic_assay", laboratory="SYNTHETIC-LAB", certificate_id=f"{config['campaign_id']}-CERT",
                       qc_type="primary", qc_flag="not_checked")
    return missing


def _fault_observations(truth: dict[str, Any], config: dict[str, Any], seed: int,
                        holes: list[dict[str, Any]], append: Callable) -> None:
    # Older campaign configurations observe contacts without requesting faults.
    settings = config.get("structures", {"observe_faults": False})
    if not settings.get("observe_faults", True):
        return
    ideal, method = config.get("ideal", False), settings.get("method", "core_logging")
    for hole in holes:
        number = 0
        for fault_index, fault in enumerate(truth.get("faults", [])):
            distance = _fault_signed_distance_m(fault, hole["x_m"], hole["y_m"], -hole.get("collar_elevation_m", 0))
            dx, dy, dz = borehole_direction(hole)
            strike, dip = math.radians(fault["strike_deg"]), math.radians(fault["dip_deg"])
            slope = -dx * math.sin(strike) + dy * math.cos(strike)
            if not math.isclose(dip, math.pi / 2):
                slope -= dz / math.tan(dip)
            width = fault["influence_width_m"]
            if abs(slope) < 1e-12:
                if abs(distance) > width:
                    continue
                top, bottom = 0.0, hole["depth_m"]
            else:
                entering, leaving = sorted(((-width - distance) / slope, (width - distance) / slope))
                top, bottom = max(0.0, entering), min(hole["depth_m"], leaving)
                if top >= bottom:
                    continue
            rng = _rng(seed, "fault-observation", hole["hole_id"], fault_index)
            if not ideal and rng.random() >= settings.get("fault_detection_probability", 1):
                continue
            shift = 0 if ideal else rng.gauss(0, settings.get("depth_sigma_m", 0))
            shift = max(-top, min(hole["depth_m"] - bottom, shift))
            top, bottom = round(top + shift, 6), min(hole["depth_m"], round(bottom + shift, 6))
            if top >= bottom:
                continue
            strike = dip = direction = None
            if method == "oriented_core":
                sigma = 0 if ideal else settings.get("orientation_sigma_deg", 0)
                strike = round((fault["strike_deg"] + rng.gauss(0, sigma)) % 360, 4) % 360
                dip = round(max(0, min(90, fault["dip_deg"] + rng.gauss(0, sigma))), 4)
                direction = (strike + 90) % 360
            number += 1
            identifier = f"{hole['hole_id']}-F{number:03d}"
            append("structural_observations", observation_id=identifier, hole_id=hole["hole_id"], depth_m=round((top + bottom) / 2, 6),
                   feature_type="fault", strike_deg=strike, dip_deg=dip, dip_direction_deg=direction,
                   confidence="high" if ideal else "medium", observation_method=method,
                   notes="Наблюдена зона нарушений в керне; продолжение за пределами скважины не определялось")
            append("fault_intersections", observation_id=identifier, hole_id=hole["hole_id"], from_m=top, to_m=bottom,
                   observation_method=method, confidence="high" if ideal else "medium", description="Интервал нарушенных пород в керне")


def _quality_controls(config: dict[str, Any], seed: int, sources: dict[str, Any], tables: dict[str, Any], append: Callable) -> None:
    settings, ideal = config["quality_control"], config.get("ideal", False)
    primaries = {(row["sample_id"], row["analyte"]): row for name in ("borehole_assays", "surface_geochemistry", "trench_samples") for row in tables[name]}
    for ordinal, (parent_id, source) in enumerate(sources.items(), 1):
        for kind, interval_key, letter in (("duplicate", "duplicate_every", "D"), ("blank", "blank_every", "B"), ("standard", "standard_every", "S")):
            every = settings.get(interval_key, 0)
            if not every or (ordinal % every and ordinal != len(sources)):
                continue
            sample_id = f"QC-{letter}-{parent_id}"
            if sample_id in sources:
                raise ValueError("Идентификатор контрольной пробы совпадает с первичной пробой")
            for analyte in source["analytes"]:
                name, limit = analyte["analyte"], analyte["detection_limit"]
                reference = 0.0 if kind == "blank" else limit * settings["standard_detection_limit_multiple"]
                if kind == "standard" and analyte["unit"].startswith("%") and reference > 100:
                    raise ValueError("Содержание процентного стандарта не может превышать 100")
                value = reference
                parent = primaries[parent_id, name]
                if kind == "duplicate":
                    value = source["grades"][name]
                    preparation = 0 if ideal else settings.get("duplicate_preparation_sigma", 0)
                    value *= math.exp(_rng(seed, "duplicate-preparation", sample_id, name).gauss(-preparation ** 2 / 2, preparation))
                    reference = parent["result_value"] if parent["result_qualifier"] != "lt" else None
                result = _laboratory_result(value, analyte, config, seed, sample_id)
                measured, qualifier = result["result_value"], result["result_qualifier"]
                absolute = relative = None
                notes = ""
                if kind == "blank":
                    acceptance = settings["blank_detection_limit_multiple"] * limit
                    acceptance_unit = analyte["unit"]
                    ratio = measured / acceptance
                    flag = "pass" if ratio <= 1 else "not_checked" if qualifier == "lt" else "warning" if ratio <= 2 else "fail"
                    absolute = measured if qualifier != "lt" else None
                else:
                    acceptance = settings[f"{kind}_tolerance_percent"]
                    acceptance_unit = "%"
                    if kind == "standard" and qualifier == "lt" and reference > 0:
                        minimum_error = 100 * max(0, reference - measured) / reference
                        flag = "fail" if minimum_error > 2 * acceptance else "warning" if minimum_error > acceptance else "not_checked"
                        notes = "Результат ниже предела обнаружения; оценка выполнена по его верхней границе"
                    elif qualifier == "lt" or reference is None:
                        flag, notes = "not_checked", "Численное сравнение ограничено пределом обнаружения"
                    else:
                        absolute = abs(measured - reference)
                        denominator = (measured + reference) / 2 if kind == "duplicate" else reference
                        relative = 100 * absolute / denominator if denominator else 0.0
                        ratio = relative / acceptance
                        flag = "pass" if ratio <= 1 else "warning" if ratio <= 2 else "fail"
                append("quality_control", control_id=f"{sample_id}-{name}", sample_id=sample_id,
                       parent_sample_id=parent_id if kind == "duplicate" else None,
                       sample_source=source["source"] if kind == "duplicate" else "laboratory",
                       hole_id=source.get("hole_id") if kind == "duplicate" else None,
                       trench_id=source.get("trench_id") if kind == "duplicate" else None,
                       qc_type=kind, analyte=name, **result, reference_value=reference,
                       reference_uncertainty=reference * settings.get("standard_uncertainty_fraction", .01) if kind == "standard" else None,
                       absolute_difference=round(absolute, 8) if absolute is not None else None,
                       relative_difference_percent=round(relative, 5) if relative is not None else None,
                       acceptance_limit=acceptance, acceptance_unit=acceptance_unit, qc_flag=flag, notes=notes or None)


def _geojson(tables: dict[str, Any], dimensions: dict[str, Any]) -> dict[str, Any]:
    common = {"type": "FeatureCollection", "schema_version": "1.0", "coordinate_system": "local_cartesian", "coordinate_unit": "m",
              "map_extent_m": {"x": [0, dimensions["width_m"]], "y": [0, dimensions["height_m"]]}}
    surface = {**common, "name": "surface_geochemistry", "vertical_reference": "depth_positive_down_from_surface", "features": []}
    for row in tables["surface_geochemistry"]:
        surface["features"].append({"type": "Feature", "id": f"{row['sample_id']}-{row['analyte']}",
                                   "geometry": {"type": "Point", "coordinates": [row["x_m"], row["y_m"]]},
                                   "properties": {key: value for key, value in row.items() if key not in {"x_m", "y_m"}}})
    trenches = {**common, "name": "trench_paths", "features": []}
    for row in tables["trenches"]:
        trenches["features"].append({"type": "Feature", "id": row["trench_id"], "geometry": {"type": "LineString", "coordinates": [
            [row["start_x_m"], row["start_y_m"]], [row["end_x_m"], row["end_y_m"]]]}, "properties": dict(row)})
    layers = {"surface_geochemistry": surface, "trench_paths": trenches}
    for name in ("outcrop_observations", "terrain_observations", "geophysical_observations"):
        features = [{"type": "Feature", "id": row["observation_id"], "geometry": {"type": "Point", "coordinates": [row["x_m"], row["y_m"]]},
                     "properties": {key: value for key, value in row.items() if key not in {"x_m", "y_m"}}} for row in tables[name]]
        layers[name] = {**common, "name": name, "features": features}
    return layers


def extend_campaign(truth: dict[str, Any], config: dict[str, Any], seed: int, holes: list[dict[str, Any]],
                    sources: dict[str, Any], tables: dict[str, Any], append: Callable) -> dict[str, Any]:
    missing_trench_samples = unavailable_soil = 0
    if _enabled(config, "structures"):
        _fault_observations(truth, config, seed, holes, append)
    if _enabled(config, "surface_geochemistry"):
        unavailable_soil = _surface_observations(truth, config, seed, sources, append)
    if _enabled(config, "trenches"):
        missing_trench_samples = _trench_observations(truth, config, seed, sources, append)
    if _enabled(config, "quality_control"):
        _quality_controls(config, seed, sources, tables, append)
    summary = {"surface_sample_count": sum(item["source"] == "surface" for item in sources.values()),
               "surface_unavailable_count": unavailable_soil,
               "outcrop_count": len(tables["outcrop_observations"]),
               "terrain_observation_count": len(tables["terrain_observations"]),
               "geophysical_observation_count": len(tables["geophysical_observations"]),
               "trench_count": len(tables["trenches"]), "trench_sample_count": sum(item["source"] == "trench" for item in sources.values()),
               "trench_missing_sample_count": missing_trench_samples,
               "fault_observation_count": len(tables["fault_intersections"]),
               "qc_sample_count": len({row["sample_id"] for row in tables["quality_control"]}),
               "qc_result_count": len(tables["quality_control"]), "total_sample_count": len(sources),
               "total_assay_count": sum(len(tables[name]) for name in ("borehole_assays", "surface_geochemistry", "trench_samples"))}
    methods = {name: {"enabled": _enabled(config, name)} for name in
               ("structures", "surface_geochemistry", "trenches", "quality_control", "outcrops", "terrain_survey", "geophysical_survey")}
    if _enabled(config, "outcrops"):
        methods["outcrops"]["point_count"] = config["outcrops"]["point_count"]
    if _enabled(config, "terrain_survey"):
        settings = config["terrain_survey"]
        methods["terrain_survey"].update({key: settings.get(key, value) for key, value in TERRAIN_SURVEY_DEFAULTS.items()},
                                         point_count=settings["point_count"], layout="grid")
    if _enabled(config, "geophysical_survey"):
        methods["geophysical_survey"].update(point_count=config["geophysical_survey"]["point_count"], layout="grid",
                                              field_available="geophysics" in truth)
    methods["structures"]["method"] = config.get("structures", {}).get("method", "core_logging")
    if _enabled(config, "trenches"):
        methods["trenches"].update({key: config["trenches"][key] for key in ("sample_length_m", "sampling_height_m")})
    methods["surface_geochemistry"]["analytes"] = [{key: item[key] for key in ("analyte", "unit", "detection_limit")} for item in config.get("surface_geochemistry", {}).get("analytes", [])]
    return {"summary": summary, "methods": methods, "geojson": _geojson(tables, truth["dimensions"])}
