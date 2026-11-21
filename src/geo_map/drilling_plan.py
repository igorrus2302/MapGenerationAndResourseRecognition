"""Place additional boreholes near anomalies in the measured surface survey."""

from __future__ import annotations

import math

from .geophysics import CHANNELS
from .recognition_geophysics import detect_geophysical_anomalies
from .recognition_spatial import add_indexed_point, index_points, nearest_point, survey_radius


DEFAULT_RANDOM_FRACTION = 0.4


def _strength(row):
    return abs(row["deviation"]) / row["deviation_threshold"]


def _select_centers(anomalies, radius, target_count):
    by_channel = {
        channel: sorted((row for row in anomalies if row["method"] == channel),
                        key=lambda row: (-_strength(row), row["observation_id"]))
        for channel in CHANNELS
    }
    # Start with the strongest channel, then give each channel a turn.
    channels = sorted((rows for rows in by_channel.values() if rows), key=lambda rows: -_strength(rows[0]))
    pending = [(iter(rows), index_points((), radius)) for rows in channels]
    limit = min(target_count, max(len(channels), math.ceil(target_count / 3)))
    centers = []
    while pending and len(centers) < limit:
        for rows, selected in pending[:]:
            center = next((row for row in rows if nearest_point(selected, (row["x_m"], row["y_m"]), radius) is None), None)
            if center is None:
                pending.remove((rows, selected))
                continue
            centers.append(center)
            add_indexed_point(selected, center, radius)
            if len(centers) == limit:
                break
    return centers


def target_boreholes(holes, bounds, dimensions, measurements, random_fraction):
    """Keep the first random holes and replace feasible later placements using measured anomalies."""
    if len(holes) < 2:
        return
    random_count = min(len(holes) - 1, max(1, math.floor(len(holes) * random_fraction + 0.5)))
    anomalies, _ = detect_geophysical_anomalies(measurements, spread_multiplier=2, uncertainty_multiplier=2)
    anomalies = [row for row in anomalies
                 if 0 <= row["x_m"] < dimensions["width_m"] and 0 <= row["y_m"] < dimensions["height_m"]]
    if not anomalies:
        return
    radius = 1.5 * survey_radius(dimensions, len(measurements))
    centers = _select_centers(anomalies, radius, len(holes) - random_count)
    # Visit all centers first, then progressively fill their neighborhoods with nearby sites.
    offsets = sorted(((x, y) for x in range(-3, 4) for y in range(-3, 4) if x*x + y*y <= 9),
                     key=lambda offset: (offset[0]**2 + offset[1]**2, offset))
    candidates = [(center["x_m"] + x * radius / 3, center["y_m"] + y * radius / 3, center)
                  for x, y in offsets for center in centers]

    def feasible_sites(limits):
        (xmin, xmax), (ymin, ymax) = limits
        return ((x, y, center) for x, y, center in candidates
                if xmin <= x <= xmax and ymin <= y <= ymax
                and x < dimensions["width_m"] and y < dimensions["height_m"])

    by_bounds = {limits: feasible_sites(limits) for limits in set(bounds)}
    separation = radius / 4
    # Reserve the random locations so a later fallback also stays clear of targeted holes.
    occupied = index_points(({**hole, "observation_id": hole["hole_id"]} for hole in holes), separation)
    for index in range(random_count, len(holes)):
        sites = by_bounds[bounds[index % len(bounds)]]
        site = next((site for site in sites if nearest_point(occupied, site[:2], separation) is None), None)
        if site is None:
            continue
        x, y, center = site
        hole = holes[index]
        hole.update(x_m=x, y_m=y, target={"observation_id": center["observation_id"], "method": center["method"]})
        add_indexed_point(occupied, {**hole, "observation_id": hole["hole_id"]}, separation)
