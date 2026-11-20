"""Associate search targets with local terrain and observed outcrops."""

from __future__ import annotations

from .recognition_spatial import index_points, nearest_point, survey_radius


BAUXITE_DEPRESSION = "terrain_bauxite_depression"
EXPOSED_HOST = "terrain_exposed_host"
TERRAIN_SIGNALS = {BAUXITE_DEPRESSION, EXPOSED_HOST}
SHALLOW_DEPTH_M = 35.0


class TerrainEvidence:
    """Only surveyed points can add terrain context or corroborate a target."""

    def __init__(self, observations):
        tables = observations["tables"]
        rows = tables.get("terrain_observations", ())
        self.radius_m = None
        if not rows:
            return
        campaign = observations["campaign"]
        survey = observations.get("plan", {}).get("methods", {}).get("terrain_survey", {})
        count = survey.get("point_count", len(rows))
        self.radius_m = survey_radius(campaign, count)
        self.terrain = index_points(rows, self.radius_m)
        self.outcrops = index_points(tables.get("outcrop_observations", ()), self.radius_m)

    def annotate(self, target, rule):
        if self.radius_m is None:
            return
        x, y, depth = target["center_xyz_m"]
        nearest = nearest_point(self.terrain, (x, y), self.radius_m)
        if not nearest:
            return
        distance, row = nearest
        terrain_type = row["terrain_type"]
        context = {key: row[key] for key in ("observation_id", "terrain_type", "surface_elevation_m", "slope_deg", "local_relief_m")}
        context["distance_xy_m"] = round(distance, 3)
        target["terrain_context"] = context

        if target["kind"] != "mineralized_interval":
            return
        depth_reference = "local_trench_surface"
        if target["source"] == "borehole":
            if target["start_xyz_m"][:2] == target["end_xyz_m"][:2]:
                depth_reference = "borehole_collar"
            elif "start_elevation_m" in target:
                elevation = (target["start_elevation_m"] + target["end_elevation_m"]) / 2
                depth = row["surface_elevation_m"] - elevation
                depth_reference = "nearest_terrain_point"
            else:
                return
        context.update(depth_below_surface_m=round(depth, 3), depth_reference=depth_reference)
        if not 0 <= depth <= SHALLOW_DEPTH_M:
            return

        signals = target["supporting_signals"]
        if target["mineral_id"] == "bauxite" and terrain_type == "depression" and "observed_contact" in signals:
            signals.append(BAUXITE_DEPRESSION)
        if terrain_type not in {"slope", "depression"}:
            return
        model = rule.get("geological_model", {})
        expected_rocks = {*model.get("host_rock_ids", ()), model.get("body_rock_id")}
        matching_rocks = expected_rocks.intersection(target["geology"]["observed_rock_ids"])
        nearby = nearest_point(self.outcrops, (x, y), self.radius_m, lambda row: row["observed_rock_id"] in matching_rocks)
        if nearby:
            outcrop_distance, outcrop = nearby
            context["outcrop"] = {"observation_id": outcrop["observation_id"], "rock_id": outcrop["observed_rock_id"],
                                  "distance_xy_m": round(outcrop_distance, 3)}
            signals.append(EXPOSED_HOST)
