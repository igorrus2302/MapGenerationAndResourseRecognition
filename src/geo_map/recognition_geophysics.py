"""Detect measured geophysical anomalies and corroborate compatible assay targets."""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from .geophysical_observations import geophysical_rows
from .geophysics import CHANNELS
from .recognition_spatial import index_points, nearest_point, survey_radius


METHOD_RULES = {"iron": ("magnetic", 150.0), "uranium": ("gamma", 2.0)}
GEOPHYSICAL_SIGNALS = {"geophysics_magnetic", "geophysics_gamma", "downhole_gamma_anomaly", "downhole_magnetic_anomaly"}
UNITS = {"magnetic": "nT", "gamma": "cps"}
FLOOR_DEVIATION = {"magnetic": 8, "gamma": 4}
MIN_MEASUREMENTS = 8


def detect_geophysical_anomalies(channels, *, spread_multiplier=3.5, uncertainty_multiplier=3):
    """Estimate channel backgrounds and detect deviations in measured survey rows."""
    anomalies, backgrounds = [], []
    for method, (field, sigma_field) in CHANNELS.items():
        usable = [row for row in channels.get(method, ()) if row.get(field) is not None]
        stats = {"method": method, "unit": UNITS[method], "measurement_count": len(usable),
                 "status": "insufficient_measurements"}
        backgrounds.append(stats)
        if len(usable) < MIN_MEASUREMENTS:
            continue
        background = median(row[field] for row in usable)
        mad = median(abs(row[field] - background) for row in usable)
        threshold = max(spread_multiplier * 1.4826 * mad,
                        uncertainty_multiplier * median(row.get(sigma_field) or 0 for row in usable),
                        FLOOR_DEVIATION[method])
        stats.update(status="estimated", median=background, mad=mad, deviation_threshold=threshold)
        for row in usable:
            delta = row[field] - background
            required = max(threshold, uncertainty_multiplier * (row.get(sigma_field) or 0))
            if (abs(delta) if method == "magnetic" else delta) < required:
                continue
            anomalies.append({"observation_id": row["observation_id"], "method": method, "unit": UNITS[method],
                              "x_m": row["x_m"], "y_m": row["y_m"], "surface_elevation_m": row.get("surface_elevation_m"),
                              "measured_value": row[field], "background_value": background,
                              "deviation": round(delta, 6), "deviation_threshold": required})
    return anomalies, backgrounds


class GeophysicalEvidence:
    def __init__(self, observations):
        channels = {method: geophysical_rows(observations["tables"], method) for method in CHANNELS}
        self.anomalies = []
        self.backgrounds = []
        self.radius_m = None
        self.radii_m = {}
        self.grids = {}
        if not any(channels.values()):
            return
        for method, rows in channels.items():
            if rows:
                self.radii_m[method] = survey_radius(observations["campaign"], len(rows))
        self.radius_m = max(self.radii_m.values())
        self.anomalies, self.backgrounds = detect_geophysical_anomalies(channels)
        for stats in self.backgrounds:
            if stats["status"] == "estimated":
                method = stats["method"]
                self.grids[method] = index_points((row for row in self.anomalies if row["method"] == method),
                                                  self.radii_m[method])

    def annotate(self, target):
        rule = METHOD_RULES.get(target.get("mineral_id"))
        if rule is None or self.radius_m is None:
            return
        method, max_depth = rule
        if method not in self.grids or "host_rock" not in target["supporting_signals"]:
            return
        # Gamma sees the top of the interval, whereas magnetic support is evaluated at its center.
        x, y, depth = target["start_xyz_m" if method == "gamma" else "center_xyz_m"]
        result = nearest_point(self.grids[method], (x, y), self.radii_m[method], lambda row: row["deviation"] > 0)
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


class DownholeGammaEvidence:
    """Use elevated measured gamma intervals as supporting evidence in the same borehole."""

    def __init__(self, observations):
        profiles = defaultdict(list)
        self.anomalies = defaultdict(list)
        for row in observations["tables"].get("downhole_gamma", ()):
            if row.get("gamma_count_rate_cps") is not None:
                profiles[row["hole_id"]].append(row)
        for hole_id, rows in profiles.items():
            if len(rows) < MIN_MEASUREMENTS:
                continue
            background = median(row["gamma_count_rate_cps"] for row in rows)
            spread = median(abs(row["gamma_count_rate_cps"] - background) for row in rows)
            threshold = max(FLOOR_DEVIATION["gamma"], 3.5 * 1.4826 * spread,
                            3 * median(row.get("gamma_sigma_cps") or 0 for row in rows))
            for row in sorted(rows, key=lambda item: item["from_m"]):
                required = max(threshold, 3 * (row.get("gamma_sigma_cps") or 0))
                if row["gamma_count_rate_cps"] - background >= required:
                    self.anomalies[hole_id].append({**row, "background_value": background,
                                                    "deviation_threshold": required})

    def annotate(self, target):
        if target["source"] != "borehole" or target.get("mineral_id") != "uranium":
            return
        matches = [row for row in self.anomalies.get(target["site_id"], ())
                   if max(row["from_m"], target["from_m"]) < min(row["to_m"], target["to_m"])]
        if matches:
            target["supporting_signals"].append("downhole_gamma_anomaly")
            peak = max(matches, key=lambda row: row["gamma_count_rate_cps"])
            target["downhole_gamma_evidence"] = {
                "measurement_ids": [row["measurement_id"] for row in matches],
                "peak_measured_cps": peak["gamma_count_rate_cps"],
                "background_cps": peak["background_value"],
            }


class DownholeMagneticEvidence:
    """Corroborate assays with positive susceptibility excursions along the same borehole."""

    FLOOR_SI = 0.001

    def __init__(self, observations, mineral_catalog, rock_catalog=None):
        self.magnetic_minerals = {item["id"] for item in mineral_catalog["minerals"]
                                  if item.get("geophysical_source", {}).get("magnetic_susceptibility_si", 0) > 0}
        self.rock_susceptibility = {item["id"]: item["geophysical_source"]["magnetic_susceptibility_si"]
                                     for item in (rock_catalog or {}).get("rocks", ())
                                     if "magnetic_susceptibility_si" in item.get("geophysical_source", {})}
        profiles, lithology = defaultdict(list), defaultdict(list)
        self.anomalies = defaultdict(list)
        self.backgrounds = []
        for row in observations["tables"].get("downhole_magnetic", ()):
            if row.get("magnetic_susceptibility_si") is not None:
                profiles[row["hole_id"]].append(row)
        for row in observations["tables"].get("borehole_lithology", ()):
            lithology[row["hole_id"]].append(row)
        for hole_id, rows in profiles.items():
            rows.sort(key=lambda row: row["from_m"])
            stats = {"hole_id": hole_id, "measurement_count": len(rows), "unit": "SI",
                     "status": "insufficient_measurements"}
            self.backgrounds.append(stats)
            if len(rows) < MIN_MEASUREMENTS:
                continue
            expected = [self._lithology_background(row, lithology[hole_id]) for row in rows]
            # Remove known rock-type contrasts when a complete lithological reference is available.
            # Otherwise use the robust measured borehole background (no ground truth is consulted).
            use_lithology = all(value is not None for value in expected)
            baseline = expected if use_lithology else [0.0] * len(rows)
            residuals = [row["magnetic_susceptibility_si"] - value for row, value in zip(rows, baseline)]
            offset = median(residuals)
            mad = median(abs(value - offset) for value in residuals)
            threshold = max(self.FLOOR_SI, 3.5 * 1.4826 * mad,
                            3 * median(row.get("magnetic_sigma_si") or 0 for row in rows))
            method = "lithology_reference" if use_lithology else "borehole_median"
            stats.update(status="estimated", background_method=method, median_residual_si=offset,
                         mad_si=mad, deviation_threshold_si=threshold)
            for row, value in zip(rows, baseline):
                background = value + offset
                deviation = row["magnetic_susceptibility_si"] - background
                required = max(threshold, 3 * (row.get("magnetic_sigma_si") or 0))
                if deviation >= required:
                    self.anomalies[hole_id].append({**row, "background_susceptibility_si": background,
                                                     "deviation_si": deviation, "deviation_threshold_si": required,
                                                     "background_method": method})

    def _lithology_background(self, row, intervals):
        start, end = row["from_m"], row["to_m"]
        weighted = covered = 0.0
        for interval in intervals:
            overlap = min(end, interval["to_m"]) - max(start, interval["from_m"])
            if overlap <= 0:
                continue
            value = self.rock_susceptibility.get(interval["observed_rock_id"])
            if value is None:
                return None
            weighted += overlap * value
            covered += overlap
        if end <= start or abs(covered - (end - start)) > 1e-6:
            return None
        return weighted / (end - start)

    def annotate(self, target):
        if target["source"] != "borehole" or target.get("mineral_id") not in self.magnetic_minerals:
            return
        matches = [row for row in self.anomalies.get(target["site_id"], ())
                   if max(row["from_m"], target["from_m"]) < min(row["to_m"], target["to_m"])]
        if not matches:
            return
        peak = max(matches, key=lambda row: row["deviation_si"])
        target["supporting_signals"].append("downhole_magnetic_anomaly")
        target["downhole_magnetic_evidence"] = {
            "measurement_ids": [row["measurement_id"] for row in matches],
            "peak_measured_si": peak["magnetic_susceptibility_si"],
            "background_si": peak["background_susceptibility_si"],
            "peak_deviation_si": peak["deviation_si"],
            "deviation_threshold_si": peak["deviation_threshold_si"],
            "background_method": peak["background_method"],
        }
