"""Spatial lookup for regularly surveyed observation points."""

from __future__ import annotations

import math
from collections import defaultdict

from .observation_tools import surface_grid_shape


def survey_radius(campaign, planned_points):
    columns, rows = surface_grid_shape(campaign, planned_points)
    return math.hypot(campaign["width_m"] / columns, campaign["height_m"] / rows) / 2


def index_points(rows, radius):
    grid = defaultdict(list)
    for row in rows:
        grid[math.floor(row["x_m"] / radius), math.floor(row["y_m"] / radius)].append(row)
    return grid


def nearest_point(grid, xy, radius, accepts=None):
    gx, gy = (math.floor(coordinate / radius) for coordinate in xy)
    candidates = []
    for i in range(gx - 1, gx + 2):
        for j in range(gy - 1, gy + 2):
            for row in grid.get((i, j), ()):
                if accepts is not None and not accepts(row):
                    continue
                distance = math.dist(xy, (row["x_m"], row["y_m"]))
                if distance <= radius:
                    candidates.append((distance, row))
    return min(candidates, key=lambda item: (item[0], item[1]["observation_id"]), default=None)
