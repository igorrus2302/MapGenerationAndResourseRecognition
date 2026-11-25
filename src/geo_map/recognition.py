"""Rank exploration targets using measured assays and observed geology."""

from __future__ import annotations

import json
import math
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from itertools import pairwise
from pathlib import Path
from statistics import median
from tempfile import NamedTemporaryFile
from typing import Any

from .boreholes import point as borehole_point
from .reconstruction import reconstruct_map
from .recognition_geophysics import GEOPHYSICAL_SIGNALS, DownholeGammaEvidence, DownholeMagneticEvidence, GeophysicalEvidence
from .recognition_terrain import SHALLOW_DEPTH_M, TERRAIN_SIGNALS, TerrainEvidence


INTERVAL_TOLERANCE_M = 1e-7
MIN_SOIL_RESULTS = 8
SOIL_BACKGROUND_RATIO = 1.35
SOIL_SIGMAS = 3.5
CORE_PROPERTY_SIGMAS = 2
STEEP_FAULT_DIP_DEG = 60
FAULT_ORIENTATION_TOLERANCE_DEG = 5

CORE_PROPERTIES = {"density_g_cm3": "density_error_g_cm3", "porosity_percent": "porosity_error_percent"}


def _analyte_key(row):
    return row["analyte"], row["unit"]


def _interval_overlaps(row, start, end):
    return max(0, min(end, row["to_m"]) - max(start, row["from_m"]))


def _measurements(rows, duplicate_qc, counts):
    for row in rows:
        if row.get("qc_type", "primary") != "primary":
            continue
        counts["primary"] += 1
        flag = duplicate_qc.get((row["sample_id"], *_analyte_key(row)))
        if flag == "fail" or row.get("qc_flag") == "fail":
            counts["failed_qc"] += 1
        elif row.get("result_qualifier") == "lt":
            counts["below_detection"] += 1
        elif row.get("result_qualifier") in (None, "", "eq"):
            counts["quantified"] += 1
            yield row


def _soil_anomalies(rows, duplicate_qc, counts):
    """Fit a background per analyte and unit using the survey itself."""
    groups = defaultdict(list)
    primary = Counter(_analyte_key(row) for row in rows if row.get("qc_type", "primary") == "primary")
    for row in _measurements(rows, duplicate_qc, counts):
        groups[_analyte_key(row)].append(row)

    backgrounds, anomalies = [], []
    for analyte, unit in sorted(primary):
        samples = groups[analyte, unit]
        n = len(samples)
        stats = {"analyte": analyte, "unit": unit, "primary_count": primary[analyte, unit], "quantified_count": n}
        backgrounds.append(stats)
        if n < MIN_SOIL_RESULTS or n * 2 <= primary[analyte, unit]:
            stats["status"] = "insufficient_quantified_results"
            continue
        background = median(row["result_value"] for row in samples)
        mad = median(abs(row["result_value"] - background) for row in samples)
        limit = median(row["detection_limit"] for row in samples)
        threshold = max(SOIL_BACKGROUND_RATIO * background, background + SOIL_SIGMAS * 1.4826 * mad, 2 * limit)
        stats.update(status="estimated", median=background, mad=mad, threshold=threshold)
        for row in samples:
            if row["result_value"] >= max(threshold, 2 * row["detection_limit"]):
                anomalies.append({"kind": "soil_anomaly", "source": "soil", "site_id": row["sample_id"],
                                  "analyte": analyte, "unit": unit, "sample_ids": [row["sample_id"]],
                                  "center_xyz_m": [row["x_m"], row["y_m"], None],
                                  "peak_result": row["result_value"], "threshold": max(threshold, 2 * row["detection_limit"])})
    return backgrounds, anomalies


def _is_steep_fault(observation):
    dip = observation["dip_deg"]
    strike, direction = observation["strike_deg"], observation["dip_direction_deg"]
    if dip is None or strike is None or direction is None:
        return False
    perpendicular_error = abs((direction - strike) % 180 - 90)
    return STEEP_FAULT_DIP_DEG <= dip <= 90 and perpendicular_error <= FAULT_ORIENTATION_TOLERANCE_DEG


def _geology_signals(rule, lithology, faults, structures, start, end):
    """Use the observed geology along this path, with distances in path metres."""
    lengths = Counter()
    for row in lithology:
        overlap = _interval_overlaps(row, start, end)
        if overlap:
            lengths[row["observed_rock_id"]] += overlap
    model = rule.get("geological_model", {})
    hosts = set(model.get("host_rock_ids", ()))
    host_length = sum(lengths[rock] for rock in hosts)
    signals = []
    if host_length >= (end - start) / 2:
        signals.append("host_rock")

    details = {"observed_rock_ids": sorted(lengths), "host_fraction": round(host_length / (end - start), 6)}
    control = model.get("control")
    if control == "fault":
        interval_ids = {row["observation_id"] for row in faults}
        crossed = {row["observation_id"] for row in faults if _interval_overlaps(row, start, end)}
        # A point in the structural log can support an intersection without a measured span.
        for row in structures:
            if (row["feature_type"] == "fault" and row["observation_id"] not in interval_ids
                    and row.get("depth_m") is not None and start <= row["depth_m"] < end):
                crossed.add(row["observation_id"])
        if crossed:
            signals.append("observed_fault")
            details["fault_observation_ids"] = sorted(crossed)
            observations = []
            for row in structures:
                if row["feature_type"] == "fault" and row["observation_id"] in crossed:
                    observed = {field: row.get(field) for field in
                                ("observation_id", "strike_deg", "dip_deg", "dip_direction_deg", "confidence")}
                    observed["distance_along_borehole_m"] = row.get("depth_m")
                    observations.append(observed)
            if observations:
                details["fault_observations"] = observations
            if model.get("geometry") == "steep_vein" and any(_is_steep_fault(row) for row in observations):
                signals.append("steep_fault")
    elif control == "contact":
        contact_rocks = set(model["contact_rock_ids"])
        buffer_m = model["contact_buffer_m"]
        contacts = []
        for left, right in pairwise(lithology):
            if abs(left["to_m"] - right["from_m"]) > INTERVAL_TOLERANCE_M:
                continue
            first, second = left["observed_rock_id"], right["observed_rock_id"]
            depth = left["to_m"]
            if (start - buffer_m <= depth <= end + buffer_m and
                    ((first in hosts and second in contact_rocks) or (second in hosts and first in contact_rocks))):
                contact = {"distance_along_path_m": depth, "rock_ids": [first, second]}
                logged = next((row for row in structures if row["feature_type"] == "contact"
                               and row.get("depth_m") is not None
                               and abs(row["depth_m"] - depth) <= INTERVAL_TOLERANCE_M), None)
                if logged:
                    contact.update(observation_id=logged["observation_id"], confidence=logged.get("confidence"))
                contacts.append(contact)
        if contacts:
            signals.append("observed_contact")
            details["contacts"] = contacts
    elif control == "intrusive" and lengths[model["body_rock_id"]] > 0:
        signals.append("intrusive_rock")
        details["body_rock_id"] = model["body_rock_id"]
    return signals, details


def _core_property_evidence(rule, lithology, measurements, rocks, start, end):
    """Compare whole-core composites with the logged mix of rocks and measurement errors."""
    model = rule.get("geological_model", {})
    relevant_rocks = set(model.get("host_rock_ids", ()))
    if model.get("body_rock_id"):
        relevant_rocks.add(model["body_rock_id"])
    compared_length = compatible_length = conflicting_length = 0.0
    checks = []
    first = bisect_right(measurements, start, key=lambda row: row["to_m"])
    stop = bisect_left(measurements, end, lo=first, key=lambda row: row["from_m"])
    for row in measurements[first:stop]:
        if row.get("qc_flag") == "fail" or any(row.get(field) is None for field in CORE_PROPERTIES):
            continue
        sample_start, sample_end = row["from_m"], row["to_m"]
        assay_start, assay_end = max(start, sample_start), min(end, sample_end)
        sample_length = sample_end - sample_start
        covered = _interval_overlaps(row, start, end)
        parts = []
        relevant_length = 0.0
        for log in lithology:
            overlap = _interval_overlaps(log, sample_start, sample_end)
            rock_id = log["observed_rock_id"]
            if overlap and rock_id in rocks:
                parts.append((overlap, rocks[rock_id]))
                if rock_id in relevant_rocks:
                    relevant_length += _interval_overlaps(log, assay_start, assay_end)
        if abs(sum(length for length, _ in parts) - sample_length) > INTERVAL_TOLERANCE_M:
            continue

        check = {"measurement_id": row["measurement_id"], "from_m": sample_start, "to_m": sample_end}
        compatible = True
        for field, error_field in CORE_PROPERTIES.items():
            bounds = [sum(length * rock[field][i] for length, rock in parts) / sample_length for i in (0, 1)]
            value = row[field]
            error = row.get(error_field) or 0.0
            tolerance = CORE_PROPERTY_SIGMAS * error + 0.000001  # Exported measurements are rounded to six digits.
            matches = bounds[0] - tolerance <= value <= bounds[1] + tolerance
            check[field] = {"observed": value, "reference_range": [round(bound, 6) for bound in bounds],
                            "measurement_sigma": error, "compatible": matches}
            compatible = compatible and matches
        compared_length += covered
        if compatible:
            compatible_length += relevant_length
        else:
            conflicting_length += covered
        checks.append(check)
    if not checks:
        return None
    supported = compatible_length >= (end - start) / 2 and conflicting_length < (end - start) / 2
    return {"supports_target": supported, "evaluated_length_m": round(compared_length, 6),
            "compatible_relevant_length_m": round(compatible_length, 6),
            "conflicting_length_m": round(conflicting_length, 6), "measurements": checks}


def _trench_point(trench, distance, sample):
    fraction = distance / trench["surveyed_length_m"]
    x = trench["start_x_m"] + fraction * (trench["end_x_m"] - trench["start_x_m"])
    y = trench["start_y_m"] + fraction * (trench["end_y_m"] - trench["start_y_m"])
    z = (sample["sampling_depth_from_m"] + sample["sampling_depth_to_m"]) / 2
    return x, y, z


def _path_targets(tables, rules, rocks, duplicate_qc, counts, source):
    if source == "borehole":
        site_field = "hole_id"
        paths, assays, logs = "borehole_collars", "borehole_assays", "borehole_lithology"
    else:
        site_field = "trench_id"
        paths, assays, logs = "trenches", "trench_samples", "trench_intervals"
    sites = {row[site_field]: row for row in tables.get(paths, ())}
    lithology, intersections = defaultdict(list), defaultdict(list)
    structures, properties = defaultdict(list), defaultdict(list)
    for row in sorted(tables.get(logs, ()), key=lambda row: row["from_m"]):
        lithology[row[site_field]].append(row)
    if source == "borehole":
        for row in tables.get("fault_intersections", ()):
            intersections[row[site_field]].append(row)
        for row in sorted(tables.get("structural_observations", ()), key=lambda row: row["observation_id"]):
            structures[row[site_field]].append(row)
        if rocks:
            intervals = (row for row in tables.get("downhole_properties", ())
                         if row.get("from_m") is not None and row.get("to_m") is not None)
            for row in sorted(intervals, key=lambda row: row["from_m"]):
                properties[row[site_field]].append(row)

    groups = defaultdict(list)
    rules_by_id = {}
    for row in _measurements(tables.get(assays, ()), duplicate_qc, counts):
        if row[site_field] not in sites:
            continue
        for rule in rules.get(_analyte_key(row), ()):
            if row["result_value"] >= rule["grade"]["display_threshold"]:
                rules_by_id[rule["id"]] = rule
                groups[row[site_field], rule["id"]].append(row)

    for (site_id, mineral_id), samples in sorted(groups.items()):
        rule = rules_by_id[mineral_id]
        analyte, unit = _analyte_key(samples[0])
        threshold = rule["grade"]["display_threshold"]
        samples.sort(key=lambda row: row["from_m"])
        # Split at every gap, including intervals where the sample was lost or failed QC.
        breaks = [0]
        for index, (left, right) in enumerate(pairwise(samples), 1):
            if abs(left["to_m"] - right["from_m"]) > INTERVAL_TOLERANCE_M:
                breaks.append(index)
        breaks.append(len(samples))
        for first, stop in pairwise(breaks):
            run = samples[first:stop]
            start, end = run[0]["from_m"], run[-1]["to_m"]
            logs = lithology[site_id]
            signals, geology = _geology_signals(rule, logs, intersections[site_id], structures[site_id], start, end)
            core_evidence = _core_property_evidence(rule, logs, properties[site_id], rocks, start, end)
            if core_evidence:
                geology["core_properties"] = core_evidence
                if core_evidence["supports_target"]:
                    signals.append("compatible_core_properties")
            if len(run) > 1:
                signals.append("adjacent_positive_samples")
            site = sites[site_id]
            elevation = {}
            if source == "borehole":
                start_point, end_point = borehole_point(site, start), borehole_point(site, end)
                if site.get("collar_elevation_m") is not None:
                    collar = site["collar_elevation_m"]
                    elevation = {"start_elevation_m": collar - start_point[2], "end_elevation_m": collar - end_point[2]}
            else:
                start_point, end_point = _trench_point(site, start, run[0]), _trench_point(site, end, run[-1])
            yield {"kind": "mineralized_interval", "source": source, "site_id": site_id,
                   "mineral_id": mineral_id, "analyte": analyte, "unit": unit,
                   "sample_ids": [row["sample_id"] for row in run], "from_m": start, "to_m": end,
                   "start_xyz_m": list(start_point), "end_xyz_m": list(end_point),
                   "center_xyz_m": [(a + b) / 2 for a, b in zip(start_point, end_point)],
                   "peak_result": max(row["result_value"] for row in run), "threshold": threshold,
                   "supporting_signals": signals, "geology": geology, **elevation}


def recognize_deposits(observations: dict[str, Any], mineral_catalog: dict[str, Any], *,
                       rock_catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Find measured intervals and surface anomalies from a public campaign bundle."""
    if observations.get("data_kind") != "exploration_observations":
        raise ValueError("Для поиска нужен сводный пакет экспедиции observations.json")
    campaign, tables = observations["campaign"], observations["tables"]
    rocks = {rock["id"]: rock for rock in (rock_catalog or {}).get("rocks", ())}
    rules_by_id = {}
    rules = defaultdict(list)
    for rule in sorted(mineral_catalog["minerals"], key=lambda rule: rule["id"]):
        threshold = rule["grade"]["display_threshold"]
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError(f"{rule['id']}: поисковый порог должен быть положительным числом")
        rules[rule["mineral"], rule["grade"]["unit"]].append(rule)
        rules_by_id[rule["id"]] = rule
    duplicate_qc, lab_alerts = {}, defaultdict(Counter)
    for row in tables.get("quality_control", ()):
        flag = row["qc_flag"]
        if flag not in ("warning", "fail"):
            continue
        key = _analyte_key(row)
        if row["qc_type"] == "duplicate":
            parent = row["parent_sample_id"], *key
            if duplicate_qc.get(parent) != "fail":
                duplicate_qc[parent] = flag
        else:
            lab_alerts[key][flag] += 1

    counts = {source: Counter() for source in ("borehole", "trench", "soil")}
    soil_rows = tables.get("surface_geochemistry", [])
    backgrounds, soil = _soil_anomalies(soil_rows, duplicate_qc, counts["soil"])
    targets = list(soil)
    for source in ("borehole", "trench"):
        targets.extend(_path_targets(tables, rules, rocks, duplicate_qc, counts[source], source))
    terrain = TerrainEvidence(observations)
    geophysics = GeophysicalEvidence(observations)
    gamma_log = DownholeGammaEvidence(observations)
    magnetic_log = DownholeMagneticEvidence(observations, mineral_catalog, rock_catalog)

    # Use the nominal surface spacing as the radius for corroboration in XY only.
    point_count = len({row["sample_id"] for row in soil_rows})
    radius = 1.5 * math.sqrt(campaign["width_m"] * campaign["height_m"] / max(point_count, 1))
    soil_grid = defaultdict(list)
    for target in soil:
        x, y, _ = target["center_xyz_m"]
        soil_grid[_analyte_key(target), math.floor(x / radius), math.floor(y / radius)].append(target)

    for target in targets:
        key = _analyte_key(target)
        x, y, _ = target["center_xyz_m"]
        gx, gy = math.floor(x / radius), math.floor(y / radius)
        nearest = min((item for i in range(gx - 1, gx + 2) for j in range(gy - 1, gy + 2)
                       for item in soil_grid.get((key, i, j), ()) if item is not target),
                      key=lambda item: (math.dist((x, y), item["center_xyz_m"][:2]), item["site_id"]), default=None)
        signals = target.setdefault("supporting_signals", [])
        if nearest:
            distance = math.dist((x, y), nearest["center_xyz_m"][:2])
            if distance <= radius:
                signals.append("nearby_soil_anomaly")
                target["nearby_soil"] = {"sample_id": nearest["site_id"], "distance_xy_m": round(distance, 3)}
        target["qc_warning_sample_ids"] = [sample for sample in target["sample_ids"]
                                          if duplicate_qc.get((sample, *key)) == "warning"]
        target["laboratory_alerts"] = dict(lab_alerts.get(key, {}))
        terrain.annotate(target, rules_by_id.get(target.get("mineral_id")))
        geophysics.annotate(target)
        gamma_log.annotate(target)
        magnetic_log.annotate(target)

    def target_order(item):
        signals = set(item["supporting_signals"])
        additional = int(bool(signals & TERRAIN_SIGNALS)) + int(bool(signals & GEOPHYSICAL_SIGNALS))
        return (item["kind"] == "soil_anomaly", -len(signals - TERRAIN_SIGNALS - GEOPHYSICAL_SIGNALS),
                -additional, -item["peak_result"] / item["threshold"],
                item["analyte"], item["site_id"], item.get("from_m", 0))

    targets.sort(key=target_order)
    for index, target in enumerate(targets, 1):
        target["target_id"] = f"TARGET-{index:04d}"
    return {
        "data_kind": "exploration_recognition", "schema_version": "1.5", "campaign": campaign,
        "reconstructed_map": reconstruct_map(observations, targets, mineral_catalog, rock_catalog=rock_catalog),
        "vertical_reference": "depth_positive_down_from_surface", "targets": targets,
        "summary": {"mineralized_intervals": len(targets) - len(soil), "soil_anomalies": len(soil),
                    "targets_with_terrain_context": sum("terrain_context" in item for item in targets),
                    "targets_supported_by_terrain": sum(not TERRAIN_SIGNALS.isdisjoint(item["supporting_signals"]) for item in targets),
                    "geophysical_anomaly_count": len(geophysics.anomalies),
                    "downhole_gamma_anomaly_count": sum(len(rows) for rows in gamma_log.anomalies.values()),
                    "targets_supported_by_downhole_gamma": sum("downhole_gamma_evidence" in item for item in targets),
                    "downhole_magnetic_anomaly_count": sum(len(rows) for rows in magnetic_log.anomalies.values()),
                    "targets_supported_by_downhole_magnetic": sum("downhole_magnetic_evidence" in item for item in targets),
                    "targets_supported_by_geophysics": sum(not GEOPHYSICAL_SIGNALS.isdisjoint(item["supporting_signals"]) for item in targets),
                    "assays_by_source": {source: {status: values[status] for status in
                                        ("primary", "quantified", "below_detection", "failed_qc")}
                                         for source, values in counts.items()}},
        "direct_thresholds": [{"mineral_id": rule["id"], "analyte": analyte, "unit": unit,
                               "threshold": rule["grade"]["display_threshold"]}
                              for (analyte, unit), definitions in sorted(rules.items()) for rule in definitions],
        "soil_backgrounds": backgrounds, "soil_support_radius_m": radius,
        "terrain_rules": {"max_depth_m": SHALLOW_DEPTH_M, "search_radius_m": terrain.radius_m},
        "geophysical_anomalies": geophysics.anomalies,
        "geophysical_backgrounds": geophysics.backgrounds,
        "downhole_magnetic_anomalies": [row for rows in magnetic_log.anomalies.values() for row in rows],
        "downhole_magnetic_backgrounds": magnetic_log.backgrounds,
        "geophysical_search_radius_m": geophysics.radius_m,
        "laboratory_alerts": [{"analyte": analyte, "unit": unit, **alerts}
                              for (analyte, unit), alerts in sorted(lab_alerts.items())],
    }


def save_recognition(result: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = NamedTemporaryFile(mode="w", dir=path.parent, encoding="utf-8", delete=False)
    temporary = Path(stream.name)
    try:
        with stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return path
