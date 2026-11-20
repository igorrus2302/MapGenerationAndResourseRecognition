from __future__ import annotations

import json
import unittest

from test_observations import ROOT, campaign_config, small_map
from geo_map.observations import generate_observations
from geo_map.recognition import recognize_deposits


class RecognitionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / "config/minerals.json").read_text(encoding="utf-8"))
        self.rocks = json.loads((ROOT / "config/rocks.json").read_text(encoding="utf-8"))
        self.observations = generate_observations(small_map(), campaign_config(), seed=1)
        self.tables = self.observations["tables"]

    def test_detects_only_intervals_supported_by_assays_from_the_generator(self):
        result = recognize_deposits(self.observations, self.catalog)
        self.assertEqual([(t["site_id"], t["from_m"], t["to_m"]) for t in result["targets"]],
                         [("BH-001", 0, 5), ("BH-001", 10, 15)])
        self.assertNotIn("SECRET-DEPOSIT", json.dumps(result))

    def test_merges_adjacent_intervals_and_leaves_failed_or_censored_gaps(self):
        assays = self.tables["borehole_assays"][:5]
        for row in assays:
            row["result_value"] = 0.5
        assays[2]["result_qualifier"] = "lt"
        self.tables["quality_control"] = [{"qc_type": "duplicate", "qc_flag": "fail",
                                           "parent_sample_id": assays[3]["sample_id"], "analyte": "Cu", "unit": "% Cu"}]
        result = recognize_deposits(self.observations, self.catalog)
        targets = result["targets"]
        self.assertEqual([(t["from_m"], t["to_m"]) for t in targets], [(0, 10), (20, 22)])
        self.assertIn("adjacent_positive_samples", targets[0]["supporting_signals"])
        self.assertEqual(result["summary"]["assays_by_source"]["borehole"]["failed_qc"], 1)

    def test_uses_measured_trajectory_and_observed_host_and_fault(self):
        hole = self.tables["borehole_collars"][0]
        hole.update(azimuth_deg=90, dip_deg=-60)
        self.tables["borehole_lithology"][0]["observed_rock_id"] = "granite"
        self.tables["fault_intersections"] = [{"observation_id": "F-01", "hole_id": hole["hole_id"], "from_m": 1, "to_m": 3}]
        assay = self.tables["borehole_assays"][0]
        assay.update(analyte="Au", unit="g/t Au", result_value=1.0)
        target = next(t for t in recognize_deposits(self.observations, self.catalog)["targets"] if t["analyte"] == "Au")
        self.assertAlmostEqual(target["end_xyz_m"][0], 7.5)
        self.assertAlmostEqual(target["end_xyz_m"][2], 4.3301270189)
        self.assertEqual(target["supporting_signals"], ["host_rock", "observed_fault"])
        self.assertEqual(target["geology"]["fault_observation_ids"], ["F-01"])

    def test_uses_fault_orientation_and_can_use_a_structural_point_without_an_interval(self):
        assay = self.tables["borehole_assays"][0]
        assay.update(analyte="Au", unit="g/t Au", result_value=1.0)
        journal = {"observation_id": "F-01", "hole_id": assay["hole_id"], "feature_type": "fault", "depth_m": 2,
                   "strike_deg": 350, "dip_deg": 65, "dip_direction_deg": 80, "confidence": "medium"}
        self.tables["structural_observations"].append(journal)

        def gold():
            return next(target for target in recognize_deposits(self.observations, self.catalog)["targets"] if target["analyte"] == "Au")

        self.assertEqual(gold()["supporting_signals"], ["observed_fault", "steep_fault"])
        self.assertEqual(gold()["geology"]["fault_observations"][0]["strike_deg"], 350)
        journal["dip_direction_deg"] = 110
        self.assertEqual(gold()["supporting_signals"], ["observed_fault"])
        journal.update(depth_m=8, dip_direction_deg=80)
        self.assertEqual(gold()["supporting_signals"], [])
        self.tables["fault_intersections"] = [{"observation_id": "F-01", "hole_id": assay["hole_id"], "from_m": 2, "to_m": 14}]
        self.assertIn("steep_fault", gold()["supporting_signals"])

    def test_core_properties_rank_compatible_intervals_and_report_conflicts(self):
        for row in self.tables["borehole_lithology"][:2]:
            row["observed_rock_id"] = "granite"
        assays = self.tables["borehole_assays"]
        assays[0]["result_value"], assays[2]["result_value"] = 0.2, 0.4
        properties = self.tables["downhole_properties"]
        properties[0].update(density_g_cm3=2.77, density_error_g_cm3=0.02, porosity_percent=1)
        properties[2].update(density_g_cm3=2.7, porosity_percent=5)

        def targets():
            return recognize_deposits(self.observations, self.catalog, rock_catalog=self.rocks)["targets"]

        first, second = targets()
        self.assertEqual((first["from_m"], second["from_m"]), (0, 10))
        self.assertIn("compatible_core_properties", first["supporting_signals"])
        self.assertNotIn("compatible_core_properties", second["supporting_signals"])
        check = second["geology"]["core_properties"]["measurements"][0]
        self.assertTrue(check["density_g_cm3"]["compatible"])
        self.assertFalse(check["porosity_percent"]["compatible"])
        properties[0]["qc_flag"] = "fail"
        self.assertEqual(targets()[0]["from_m"], 10)
        self.assertNotIn("core_properties", targets()[1]["geology"])

    def test_composites_rock_ranges_and_links_the_logged_contact(self):
        logs = self.tables["borehole_lithology"]
        logs[0].update(to_m=2.5, observed_rock_id="limestone")
        logs[1].update(from_m=2.5, observed_rock_id="claystone")
        self.tables["structural_observations"][0]["depth_m"] = 2.5
        self.tables["borehole_assays"][0].update(analyte="Al₂O₃", unit="% Al₂O₃", result_value=12)
        measured = self.tables["downhole_properties"][0]
        measured.update(density_g_cm3=2.4, porosity_percent=12)
        result = recognize_deposits(self.observations, self.catalog, rock_catalog=self.rocks)
        target = next(t for t in result["targets"] if t["analyte"] == "Al₂O₃")
        details = target["geology"]
        contact = details["contacts"][0]
        self.assertEqual(contact["observation_id"], self.tables["structural_observations"][0]["observation_id"])
        ranges = {rock["id"]: rock["density_g_cm3"] for rock in self.rocks["rocks"]}
        expected = [(first + second) / 2 for first, second in zip(ranges["limestone"], ranges["claystone"])]
        self.assertEqual(details["core_properties"]["measurements"][0]["density_g_cm3"]["reference_range"], expected)
        self.assertIn("compatible_core_properties", target["supporting_signals"])

    def test_soil_background_requires_data_and_anomaly_has_no_target_depth(self):
        self.tables["surface_geochemistry"] = [
            {"sample_id": f"SG-{i}", "x_m": i, "y_m": 1, "analyte": "Cu", "unit": "% Cu",
             "result_qualifier": None, "result_value": 0.005 if i == 5 else 0.002, "detection_limit": 0.0005}
            for i in range(8)
        ]
        result = recognize_deposits(self.observations, self.catalog)
        soil = [t for t in result["targets"] if t["kind"] == "soil_anomaly"]
        self.assertEqual([t["center_xyz_m"] for t in soil], [[5, 1, None]])
        self.assertIn("nearby_soil_anomaly", result["targets"][0]["supporting_signals"])
        self.tables["surface_geochemistry"].pop()
        result = recognize_deposits(self.observations, self.catalog)
        self.assertEqual(result["summary"]["soil_anomalies"], 0)
        self.assertEqual(result["soil_backgrounds"][0]["status"], "insufficient_quantified_results")

    def test_trench_uses_path_geometry_and_matching_observed_contact(self):
        self.tables["trenches"] = [{"trench_id": "TR-1", "start_x_m": 3, "start_y_m": 2,
                                   "end_x_m": 3, "end_y_m": 12, "surveyed_length_m": 10}]
        self.tables["trench_intervals"] = [
            {"trench_id": "TR-1", "from_m": 0, "to_m": 5, "observed_rock_id": "limestone"},
            {"trench_id": "TR-1", "from_m": 5, "to_m": 10, "observed_rock_id": "claystone"},
        ]
        sample = {"trench_id": "TR-1", "sample_id": "TR-S1", "from_m": 1, "to_m": 4, "analyte": "Al₂O₃",
                  "unit": "% Al₂O₃", "sampling_depth_from_m": 1.8, "sampling_depth_to_m": 2, "result_value": 15}
        self.tables["trench_samples"] = [sample, {**sample, "sample_id": "TR-S2", "unit": "ppm"}]
        targets = [t for t in recognize_deposits(self.observations, self.catalog)["targets"] if t["source"] == "trench"]
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["start_xyz_m"], [3, 3, 1.9])
        self.assertEqual(targets[0]["end_xyz_m"], [3, 6, 1.9])
        self.assertEqual(targets[0]["supporting_signals"], ["host_rock", "observed_contact"])

    def test_bauxite_depression_prefers_shallow_observed_carbonate_contact(self):
        for log in self.tables["borehole_lithology"]:
            log["observed_rock_id"] = "limestone" if log["from_m"] == 0 else "claystone"
        assays = [row for row in self.tables["borehole_assays"] if row["from_m"] == 0]
        for row, grade in zip(assays, (12, 20)):
            row.update(analyte="Al₂O₃", unit="% Al₂O₃", result_value=grade)
        self.tables["terrain_observations"] = [
            {"observation_id": "TER-1", "x_m": 5, "y_m": 5, "terrain_type": "depression",
             "slope_deg": 2, "local_relief_m": -4, "surface_elevation_m": 0},
            {"observation_id": "TER-2", "x_m": 15, "y_m": 5, "terrain_type": "flat",
             "slope_deg": 1, "local_relief_m": 0, "surface_elevation_m": 0},
        ]
        result = recognize_deposits(self.observations, self.catalog)
        bauxite = [target for target in result["targets"] if target["mineral_id"] == "bauxite"]
        self.assertEqual([target["site_id"] for target in bauxite], ["BH-001", "BH-002"])
        self.assertIn("terrain_bauxite_depression", bauxite[0]["supporting_signals"])
        self.assertNotIn("terrain_bauxite_depression", bauxite[1]["supporting_signals"])
        self.assertEqual(result["summary"]["targets_supported_by_terrain"], 1)
        self.tables["borehole_lithology"][1]["observed_rock_id"] = "granite"
        result = recognize_deposits(self.observations, self.catalog)
        self.assertEqual(result["summary"]["targets_supported_by_terrain"], 0)
        assays[0]["result_qualifier"] = "lt"
        result = recognize_deposits(self.observations, self.catalog)
        self.assertFalse(any(t["mineral_id"] == "bauxite" and t["site_id"] == "BH-001" for t in result["targets"]))

    def test_slope_outcrop_requires_close_matching_rock_and_shallow_projected_depth(self):
        hole = self.tables["borehole_collars"][0]
        hole.update(azimuth_deg=90, dip_deg=-60, collar_elevation_m=0)
        self.tables["borehole_lithology"][0]["observed_rock_id"] = "granite"
        terrain = {"observation_id": "TER-1", "x_m": 6, "y_m": 5, "terrain_type": "slope",
                   "slope_deg": 15, "local_relief_m": 0, "surface_elevation_m": 3}
        exposure = {"observation_id": "OUT-1", "x_m": 6, "y_m": 5, "observed_rock_id": "granite"}
        self.tables["terrain_observations"] = [terrain]
        self.tables["outcrop_observations"] = [exposure]

        def shallow_target():
            return next(t for t in recognize_deposits(self.observations, self.catalog)["targets"] if t["from_m"] == 0)

        target = shallow_target()
        self.assertIn("terrain_exposed_host", target["supporting_signals"])
        self.assertEqual(target["terrain_context"]["outcrop"]["observation_id"], "OUT-1")
        self.assertAlmostEqual(target["terrain_context"]["depth_below_surface_m"], 5.165)
        terrain["surface_elevation_m"] = 40
        self.assertNotIn("terrain_exposed_host", shallow_target()["supporting_signals"])
        terrain["surface_elevation_m"] = 3
        exposure["observed_rock_id"] = "diorite"  # Suitable for copper, but absent from this interval.
        self.assertNotIn("terrain_exposed_host", shallow_target()["supporting_signals"])
        exposure.update(x_m=19, observed_rock_id="granite")
        self.assertNotIn("terrain_exposed_host", shallow_target()["supporting_signals"])
        terrain["x_m"] = 19
        self.assertNotIn("terrain_context", shallow_target())


if __name__ == "__main__":
    unittest.main()
