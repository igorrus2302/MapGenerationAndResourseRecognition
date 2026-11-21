"""Detect measured geophysical anomalies and corroborate compatible assay targets."""

from __future__ import annotations

from statistics import median

from .geophysics import CHANNELS
from .recognition_spatial import index_points, nearest_point, survey_radius


METHOD_RULES = {"iron": ("magnetic", 150.0), "uranium": ("gamma", 2.0)}
GEOPHYSICAL_SIGNALS = {"geophysics_magnetic", "geophysics_gamma"}
UNITS = {"magnetic": "nT", "gamma": "cps"}
FLOOR_DEVIATION = {"magnetic": 8, "gamma": 4}
MIN_MEASUREMENTS = 8


def detect_geophysical_anomalies(rows, *, spread_multiplier=3.5, uncertainty_multiplier=3):
    """Estimate channel backgrounds and detect deviations in measured survey rows."""
    anomalies, backgrounds = [], []
    for method, (field, sigma_field) in CHANNELS.items():
        usable = [row for row in rows if row.get(field) is not None]
        stats = {"method": method, "unit": UNITS[method], "measurement_count": len(usable),
                 "status": "insufficient_measurements"}
        backgrounds.append(stats)
        if len(usable) < MIN_MEASUREMENTS:
            continue
        background = median(row[field] for row in usable)
        mad = median(abs(row[field] - background) for row in usable)
        threshold = max(spread_multiplier * 1.4826 * mad,
                        uncertainty_multiplier * median(row.get(sigma_field, 0) for row in usable),
                        FLOOR_DEVIATION[method])
        stats.update(status="estimated", median=background, mad=mad, deviation_threshold=threshold)
        for row in usable:
            delta = row[field] - background
            required = max(threshold, uncertainty_multiplier * row.get(sigma_field, 0))
            if (abs(delta) if method == "magnetic" else delta) < required:
                continue
            anomalies.append({"observation_id": row["observation_id"], "method": method, "unit": UNITS[method],
                              "x_m": row["x_m"], "y_m": row["y_m"], "surface_elevation_m": row.get("surface_elevation_m"),
                              "measured_value": row[field], "background_value": background,
                              "deviation": round(delta, 6), "deviation_threshold": required})
    return anomalies, backgrounds


class GeophysicalEvidence:
    def __init__(self, observations):
        rows = observations["tables"].get("geophysical_observations", ())
        self.anomalies = []
        self.backgrounds = []
        self.radius_m = None
        self.grids = {}
        if not rows:
            return
        plan = observations.get("plan", {}).get("methods", {}).get("geophysical_survey", {})
        self.radius_m = survey_radius(observations["campaign"], plan.get("point_count", len(rows)))
        self.anomalies, self.backgrounds = detect_geophysical_anomalies(rows)
        for stats in self.backgrounds:
            if stats["status"] == "estimated":
                method = stats["method"]
                self.grids[method] = index_points((row for row in self.anomalies if row["method"] == method),
                                                  self.radius_m)

    def annotate(self, target):
        rule = METHOD_RULES.get(target.get("mineral_id"))
        if rule is None or self.radius_m is None:
            return
        method, max_depth = rule
        if method not in self.grids or "host_rock" not in target["supporting_signals"]:
            return
        # Gamma sees the top of the interval, whereas magnetic support is evaluated at its center.
        x, y, depth = target["start_xyz_m" if method == "gamma" else "center_xyz_m"]
        result = nearest_point(self.grids[method], (x, y), self.radius_m, lambda row: row["deviation"] > 0)
        if not result:
            return
        distance, anomaly = result
        if target["source"] == "borehole" and target["start_xyz_m"][:2] != target["end_xyz_m"][:2]:
            elevation = target.get("start_elevation_m")
            surface = anomaly["surface_elevation_m"]
            if elevation is None or surface is None or (method == "gamma" and distance > 5):
                return
            if method == "magnetic":
                elevation = (elevation + target["end_elevation_m"]) / 2
            depth = surface - elevation
        if 0 <= depth <= max_depth:
            target["supporting_signals"].append(f"geophysics_{method}")
            target["geophysical_evidence"] = {**anomaly, "distance_xy_m": round(distance, 3),
                                              "depth_below_surface_m": round(depth, 3)}
