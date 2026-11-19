"""Sampling and measurement primitives shared by observation models."""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any

from .boreholes import direction, point, validate_trajectory


def measure_grade(value: float, analyte: dict[str, Any], noise: dict[str, Any], seed: int,
                  sample_id: str, *, ideal: bool = False, bias_fraction: float = 0,
                  contamination_limits: float = 0) -> dict[str, Any]:
    """One laboratory model for primary samples and all control materials."""
    rng = _rng(seed, "assay", sample_id, analyte["analyte"])
    relative = 0 if ideal else noise.get("assay_relative_sigma", 0)
    if not ideal:
        value = value * (1 + bias_fraction) + contamination_limits * analyte["detection_limit"]
    value *= math.exp(rng.gauss(-relative * relative / 2, relative))
    limit = analyte["detection_limit"]
    additive = 0 if ideal else limit * noise.get("assay_detection_limit_sigma_fraction", 0)
    value = max(0.0, value + rng.gauss(0, additive))
    if analyte["unit"].startswith("%"):
        value = min(100.0, value)
    below = not ideal and value < limit
    return {"result_value": limit if below else round(value, 8),
            "result_qualifier": "lt" if below else None,
            "unit": analyte["unit"], "detection_limit": limit}


def _rng(seed: int, *parts: object) -> random.Random:
    key = json.dumps([seed, *parts], ensure_ascii=False, separators=(",", ":"))
    return random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest(), "big"))


def _number(value: Any, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: требуется число")
    number = float(value)
    if not math.isfinite(number) or number < 0 or (positive and number == 0):
        raise ValueError(f"{name}: требуется конечное {'положительное' if positive else 'неотрицательное'} число")
    return number


def _trace_edges(cuts: set[float]) -> list[float]:
    """Merge numerically simultaneous crossings without discarding thin intervals."""
    ordered = sorted(cuts)
    edges = [ordered[0]]
    for value in ordered[1:-1]:
        tolerance = 16 * max(math.ulp(value), math.ulp(edges[-1]), math.ulp(ordered[-1]))
        if value - edges[-1] > tolerance and ordered[-1] - value > tolerance:
            edges.append(value)
    return [*edges, ordered[-1]]


class TruthSampler:
    """Internal sampler. None of its source records are exported as observations."""

    def __init__(self, truth_map: dict[str, Any]):
        self.dimensions = truth_map["dimensions"]
        self.cells = {(cell["x_index"], cell["y_index"]): cell for cell in truth_map["cells"]}

    def column(self, x_m: float, y_m: float) -> dict[str, Any]:
        dims = self.dimensions
        if not (math.isfinite(x_m) and math.isfinite(y_m) and 0 <= x_m < dims["width_m"] and 0 <= y_m < dims["height_m"]):
            raise ValueError("Точка наблюдения находится вне карты")
        step = dims["cell_size_m"]
        return self.cells[math.floor(x_m / step), math.floor(y_m / step)]

    def segments(self, x_m: float, y_m: float, from_m: float, to_m: float) -> list[dict[str, Any]]:
        if not 0 <= from_m < to_m <= self.dimensions["depth_m"]:
            raise ValueError("Недопустимый интервал опробования")
        cell = self.column(x_m, y_m)
        cuts = {from_m, to_m}
        for interval in [*cell["intervals"], *cell["mineralization"]]:
            for key in ("from_depth_m", "to_depth_m"):
                if from_m < interval[key] < to_m:
                    cuts.add(interval[key])
        result = []
        edges = sorted(cuts)
        for start, end in zip(edges, edges[1:]):
            middle = (start + end) / 2
            rock = next((item for item in cell["intervals"] if item["from_depth_m"] <= middle < item["to_depth_m"]), None)
            if rock is None:
                raise ValueError("Истинная карта содержит разрыв в интервалах пород")
            result.append({
                "from_m": start, "to_m": end, "rock_id": rock["rock_id"],
                "length_m": end - start,
                "properties": rock["properties"],
                "mineralization": [item for item in cell["mineralization"] if item["from_depth_m"] <= middle < item["to_depth_m"]],
            })
        return result

    def borehole_segments(self, hole: dict[str, Any], from_m: float, to_m: float) -> list[dict[str, Any]]:
        """Split a straight core exactly at XY cells, rock and mineral boundaries."""
        if not 0 <= from_m < to_m <= hole["depth_m"]:
            raise ValueError("Недопустимый интервал вдоль ствола скважины")
        validate_trajectory(hole, self.dimensions)
        dx, dy, dz = direction(hole)
        horizontal_cuts = {from_m, to_m}
        step = self.dimensions["cell_size_m"]
        for origin, velocity in ((hole["x_m"], dx), (hole["y_m"], dy)):
            if velocity == 0:
                continue
            low, high = sorted((origin + from_m * velocity, origin + to_m * velocity))
            for index in range(math.floor(low / step) + 1, math.ceil(high / step)):
                crossing = (index * step - origin) / velocity
                if from_m < crossing < to_m:
                    horizontal_cuts.add(crossing)
        result = []
        edges = _trace_edges(horizontal_cuts)
        for start, end in zip(edges, edges[1:]):
            x, y, _ = point(hole, (start + end) / 2)
            # A boundary endpoint can round a few ulps outside the model.
            x = min(math.nextafter(self.dimensions["width_m"], -math.inf), max(0.0, x))
            y = min(math.nextafter(self.dimensions["height_m"], -math.inf), max(0.0, y))
            cell = self.column(x, y)
            cuts = {start, end}
            for interval in [*cell["intervals"], *cell["mineralization"]]:
                for key in ("from_depth_m", "to_depth_m"):
                    crossing = interval[key] / dz
                    if start < crossing < end:
                        cuts.add(crossing)
            boundaries = _trace_edges(cuts)
            for top, bottom in zip(boundaries, boundaries[1:]):
                depth = (top + bottom) / 2 * dz
                rock = next((item for item in cell["intervals"] if item["from_depth_m"] <= depth < item["to_depth_m"]), None)
                if rock is None:
                    raise ValueError("Истинная карта содержит разрыв в интервалах пород")
                result.append({"from_m": top, "to_m": bottom, "length_m": bottom - top,
                               "rock_id": rock["rock_id"], "properties": rock["properties"],
                               "mineralization": [item for item in cell["mineralization"] if item["from_depth_m"] <= depth < item["to_depth_m"]]})
        return result

    def sample(self, x_m: float, y_m: float, from_m: float, to_m: float, analytes: list[dict[str, Any]]) -> dict[str, Any]:
        segments = self.segments(x_m, y_m, from_m, to_m)
        return self._composite(segments, to_m - from_m, analytes)

    def sample_borehole(self, hole: dict[str, Any], from_m: float, to_m: float, analytes: list[dict[str, Any]]) -> dict[str, Any]:
        return self._composite(self.borehole_segments(hole, from_m, to_m), to_m - from_m, analytes)

    @staticmethod
    def _composite(segments: list[dict[str, Any]], length_m: float, analytes: list[dict[str, Any]]) -> dict[str, Any]:
        total_mass = sum(part["length_m"] * part["properties"]["density_g_cm3"] for part in segments)
        if total_mass <= 0:
            raise ValueError("Для опробования нужна положительная плотность")
        grades = {}
        for analyte in analytes:
            mass_grade = 0.0
            for part in segments:
                matches = [item for item in part["mineralization"] if item["mineral"] == analyte["analyte"]]
                if any(item["grade_unit"] != analyte["unit"] for item in matches):
                    raise ValueError(f"Несовместимые единицы для {analyte['analyte']}")
                grade = sum(item["average_grade"] for item in matches)
                mass_grade += grade * part["length_m"] * part["properties"]["density_g_cm3"]
            grades[analyte["analyte"]] = mass_grade / total_mass
        return {
            "grades": grades,
            "density_g_cm3": total_mass / length_m,
            "porosity_percent": sum(part["length_m"] * part["properties"]["porosity_percent"] for part in segments) / length_m,
        }


