"""Straight boreholes in local coordinates; distances are measured along the core."""

from __future__ import annotations

import math
from typing import Any


def orientation(settings: dict[str, Any]) -> dict[str, float]:
    values = {"azimuth_deg": settings.get("azimuth_deg", 0), "dip_deg": settings.get("dip_deg", -90)}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{key}: требуется конечное число")
    if not 0 <= values["azimuth_deg"] < 360:
        raise ValueError("azimuth_deg должен лежать в [0, 360)")
    if not -90 <= values["dip_deg"] < 0:
        raise ValueError("dip_deg должен лежать в [-90, 0): бурение направлено вниз")
    if math.radians(values["dip_deg"]) == 0:
        raise ValueError("dip_deg слишком мал для расчёта траектории")
    return values


def direction(hole: dict[str, Any]) -> tuple[float, float, float]:
    """Azimuth is clockwise from +Y (north), dip is negative below horizontal."""
    azimuth, dip = math.radians(hole.get("azimuth_deg", 0)), math.radians(hole.get("dip_deg", -90))
    horizontal = 0.0 if hole.get("dip_deg", -90) == -90 else math.cos(dip)
    x, y = horizontal * math.sin(azimuth), horizontal * math.cos(azimuth)
    # Cardinal directions must not drift into an adjacent column at its boundary.
    return (0.0 if abs(x) < 1e-15 else x, 0.0 if abs(y) < 1e-15 else y, -math.sin(dip))


def point(hole: dict[str, Any], measured_depth_m: float) -> tuple[float, float, float]:
    dx, dy, dz = direction(hole)
    return hole["x_m"] + dx * measured_depth_m, hole["y_m"] + dy * measured_depth_m, dz * measured_depth_m


def validate_trajectory(hole: dict[str, Any], dimensions: dict[str, Any]) -> None:
    """Endpoints suffice to check a straight line against the rectangular map."""
    if not (0 <= hole["x_m"] < dimensions["width_m"] and 0 <= hole["y_m"] < dimensions["height_m"]):
        raise ValueError(f"{hole['hole_id']}: устье скважины выходит за границы карты")
    end = point(hole, hole["depth_m"])
    for coordinate, limit in zip(end, (dimensions["width_m"], dimensions["height_m"], dimensions["depth_m"])):
        if not -1e-9 <= coordinate <= limit + 1e-9:
            raise ValueError(f"{hole['hole_id']}: траектория скважины выходит за границы карты")


def collar_bounds(dimensions: dict[str, Any], length: float, angles: dict[str, Any]) -> tuple[tuple[float, float], tuple[float, float]]:
    """Feasible collar rectangle for automatic placement, independent of geology."""
    dx, dy, dz = direction(angles)
    if dz * length > dimensions["depth_m"] + 1e-9:
        raise ValueError("Вертикальная глубина скважины превышает глубину истинной карты")
    bounds = []
    for delta, limit in ((dx * length, dimensions["width_m"]), (dy * length, dimensions["height_m"])):
        low, high = max(0.0, -delta), min(limit, limit - delta)
        if low >= high:
            raise ValueError("Для заданных длины и наклона скважины нет места в границах карты")
        bounds.append((low, high))
    return bounds[0], bounds[1]
