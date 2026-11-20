from __future__ import annotations

import json
import math
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from test_observations import campaign_config, small_map
from geo_map.observations import generate_observations, save_observations
from geo_map.observation_models import SurfaceModel
from geo_map.observation_tools import TruthSampler


def extended_map() -> dict:
    truth = small_map()
    truth["rocks"].append({"id": "soil", "name": "Почва", "category": "surface", "color": "#826748"})
    for cell in truth["cells"]:
        cell["intervals"][0]["from_depth_m"] = 1
        cell["intervals"].insert(0, {"from_depth_m": 0, "to_depth_m": 1, "rock_id": "soil", "properties": {"density_g_cm3": 1.5, "porosity_percent": 40}})
    truth["faults"] = [
        {"id": "SECRET-FAULT", "trace_center_m": [5, 0], "strike_deg": 0, "dip_deg": 45, "dip_direction_deg": 90, "influence_width_m": 1, "vertical_displacement_m": 10},
        {"id": "OUTSIDE-FAULT", "trace_center_m": [5, 50], "strike_deg": 0, "dip_deg": 45, "dip_direction_deg": 90, "influence_width_m": 1, "vertical_displacement_m": 10},
    ]
    return truth


def extended_config() -> dict:
    config = campaign_config()
    config["structures"] = {"enabled": True, "observe_contacts": True, "observe_faults": True,
                            "method": "oriented_core", "fault_detection_probability": 1, "depth_sigma_m": 0, "orientation_sigma_deg": 0}
    config["surface_geochemistry"] = {
        "enabled": True, "layout": "manual", "points": [{"sample_id": "SG-001", "x_m": 5, "y_m": 5}, {"sample_id": "SG-002", "x_m": 15, "y_m": 5}],
        "sampling_depth_from_m": .2, "sampling_depth_to_m": .4, "position_sigma_m": 0,
        "analytes": [{"analyte": "Cu", "unit": "% Cu", "detection_limit": .001, "background_grade": .01,
                      "response_factor": .1, "depth_decay_m": 10, "lateral_spread_m": 5, "background_scale_m": 10, "background_variation_fraction": .3}],
    }
    config["trenches"] = {"enabled": True, "layout": "manual", "depth_m": .5, "width_m": 1,
                          "sample_length_m": 5, "sampling_height_m": .2, "position_sigma_m": 0,
                          "paths": [{"trench_id": "TR-001", "start_x_m": 0, "start_y_m": 5, "end_x_m": 20, "end_y_m": 5}]}
    config["quality_control"] = {"enabled": True, "duplicate_every": 2, "blank_every": 2, "standard_every": 2,
                                 "duplicate_preparation_sigma": 0, "duplicate_tolerance_percent": 20, "standard_tolerance_percent": 10,
                                 "blank_detection_limit_multiple": 3, "standard_detection_limit_multiple": 100,
                                 "standard_uncertainty_fraction": .01, "batch_bias_fraction": 0, "contamination_detection_limits": 0}
    return config


class ExtendedObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.truth, self.config = extended_map(), extended_config()

    def generate(self, seed=1):
        return generate_observations(self.truth, self.config, seed=seed)

    def test_terrain_survey_classifies_measured_profile_and_exports_records(self):
        truth = small_map()
        heights = (4, 4, 9, 4, 4, 4, -1, 4, 4)
        template = truth["cells"][1]
        truth["dimensions"].update(width_cells=len(heights), width_m=10 * len(heights))
        truth["cells"] = []
        for index, elevation in enumerate(heights):
            cell = deepcopy(template)
            cell.update(x_index=index, surface_elevation_m=elevation)
            cell["intervals"][0]["from_depth_m"] = -elevation
            truth["cells"].append(cell)
        config = campaign_config()
        config["terrain_survey"] = {"enabled": True, "point_count": len(heights), "elevation_sigma_m": 0.25}
        bundle = generate_observations(truth, config, seed=200)
        rows = bundle["tables"]["terrain_observations"]
        self.assertEqual([row["surface_elevation_m"] for row in rows], list(heights))
        self.assertEqual([row["terrain_type"] for row in rows],
                         ["flat", "slope", "hill", "slope", "flat", "slope", "depression", "slope", "flat"])
        self.assertEqual((rows[2]["slope_deg"], rows[2]["local_relief_m"], rows[6]["local_relief_m"]), (0, 5, -5))
        self.assertEqual(rows[0]["elevation_uncertainty_m"], 0)
        self.assertEqual(bundle["summary"]["terrain_observation_count"], len(heights))
        with tempfile.TemporaryDirectory() as folder:
            directory = save_observations(bundle, folder).parent
            item = directory / "objects/terrain/TER-0003.json"
            self.assertEqual(json.loads(item.read_text())["tables"]["terrain_observations"], [rows[2]])
            path = directory / "tables/terrain/terrain_observations.geojson"
            features = json.loads(path.read_text())["features"]
            self.assertEqual(features[6]["geometry"]["coordinates"], [65, 5])
            self.assertEqual(features[6]["properties"]["terrain_type"], "depression")

    def test_isolated_terrain_point_has_no_estimated_class(self):
        self.config["terrain_survey"] = {"enabled": True, "point_count": 1}
        row, = self.generate()["tables"]["terrain_observations"]
        self.assertEqual((row["slope_deg"], row["local_relief_m"], row["terrain_type"]), (None, None, "undetermined"))

    def test_relief_shifts_sampling_and_exports_only_surveyed_exposures(self):
        self.truth["terrain"] = {"surface_cover_rock_id": "soil", "min_elevation_m": -3, "max_elevation_m": 5}
        hill, valley = self.truth["cells"]
        hill["surface_elevation_m"] = 5
        hill["intervals"][0].update(from_depth_m=-5, to_depth_m=-4)
        hill["intervals"][1]["from_depth_m"] = -4
        valley["surface_elevation_m"] = -3
        valley["intervals"].pop(0)
        valley["intervals"][0]["from_depth_m"] = 3
        self.config["drilling"]["holes"][0].update(azimuth_deg=90, dip_deg=-60, depth_m=20)
        self.config["outcrops"] = {"enabled": True, "point_count": 2}
        bundle = self.generate()
        tables = bundle["tables"]
        self.assertEqual([row["collar_elevation_m"] for row in tables["borehole_collars"]], [5, -3])
        self.assertEqual(bundle["summary"]["surface_unavailable_count"], 1)
        self.assertEqual(bundle["summary"]["surface_sample_count"], 1)
        exposure, = tables["outcrop_observations"]
        self.assertEqual((exposure["observation_id"], exposure["x_m"], exposure["surface_elevation_m"], exposure["observed_rock_id"]),
                         ("OUT-0002", 15, -3, "a"))
        self.assertEqual([row["sample_material"] for row in tables["trench_intervals"]], ["soil", "rock"])
        hole = self.config["drilling"]["holes"][0]
        grade = TruthSampler(self.truth).sample_borehole(hole, 8, 10, self.config["analytes"])["grades"]["Cu"]
        self.assertGreater(grade, 0)
        with tempfile.TemporaryDirectory() as folder:
            directory = save_observations(bundle, folder).parent
            path = directory / "tables/outcrops/outcrop_observations.geojson"
            feature, = json.loads(path.read_text())["features"]
            self.assertEqual(feature["geometry"]["coordinates"], [15, 5])
            obj = directory / "objects/outcrops/OUT-0002.json"
            self.assertEqual(json.loads(obj.read_text())["tables"]["outcrop_observations"], [exposure])

    def test_all_four_methods_produce_linked_observations(self):
        bundle = self.generate()
        summary, tables = bundle["summary"], bundle["tables"]
        self.assertEqual(summary["surface_sample_count"], 2)
        self.assertEqual(summary["trench_count"], 1)
        self.assertEqual(summary["trench_sample_count"], 4)
        self.assertEqual(summary["fault_observation_count"], 2)
        self.assertGreater(summary["qc_sample_count"], 0)
        self.assertEqual(summary["total_sample_count"], 16)
        self.assertEqual(summary["total_assay_count"], 16)
        structure_ids = {row["observation_id"] for row in tables["structural_observations"] if row["feature_type"] == "fault"}
        self.assertEqual(structure_ids, {row["observation_id"] for row in tables["fault_intersections"]})
        self.assertEqual(self.truth, extended_map())
        self.assertEqual(self.config, extended_config())

    def test_faults_are_clipped_to_real_intersections_and_orientation_method(self):
        bundle = self.generate()
        for row in bundle["tables"]["fault_intersections"]:
            self.assertAlmostEqual(row["from_m"], 4)
            self.assertAlmostEqual(row["to_m"], 6)
        faults = [row for row in bundle["tables"]["structural_observations"] if row["feature_type"] == "fault"]
        self.assertEqual(len(faults), 2)
        for row in faults:
            self.assertEqual((row["strike_deg"], row["dip_deg"], row["dip_direction_deg"]), (0, 45, 90))
            self.assertIsNone(row["offset_estimate_m"])
        self.config["structures"]["method"] = "core_logging"
        for row in self.generate()["tables"]["structural_observations"]:
            self.assertIsNone(row["strike_deg"])
            self.assertIsNone(row["dip_deg"])

    def test_fault_detection_and_noisy_orientation_stay_in_bounds(self):
        self.config["ideal"] = False
        self.config["structures"].update(fault_detection_probability=0)
        self.assertEqual(self.generate()["summary"]["fault_observation_count"], 0)
        self.config["structures"].update(fault_detection_probability=1, depth_sigma_m=100, orientation_sigma_deg=500)
        bundle = self.generate()
        for row in bundle["tables"]["fault_intersections"]:
            self.assertTrue(0 <= row["from_m"] < row["to_m"] <= 22)
        for row in bundle["tables"]["structural_observations"]:
            if row["feature_type"] == "fault":
                self.assertTrue(0 <= row["strike_deg"] < 360)
                self.assertTrue(0 <= row["dip_deg"] <= 90)
                self.assertEqual(row["dip_direction_deg"], (row["strike_deg"] + 90) % 360)

    def test_background_is_stable_between_campaigns_and_ignores_run_metadata(self):
        self.config["ideal"] = False
        self.config["noise"] = {}
        first = self.generate(1)["tables"]["surface_geochemistry"]
        self.truth["seed"] = 999
        self.truth["generated_at"] = "a different run"
        self.config["campaign_id"] = "SECOND"
        second = self.generate(987)["tables"]["surface_geochemistry"]
        self.assertEqual([row["result_value"] for row in first], [row["result_value"] for row in second])
        self.assertEqual([row["x_m"] for row in first], [row["x_m"] for row in second])

    def test_surface_signal_decays_with_depth_and_spreads_laterally(self):
        analyte = deepcopy(self.config["surface_geochemistry"]["analytes"][0])
        analyte.update(background_grade=0, response_factor=1)
        shallow = deepcopy(self.truth)
        shallow["cells"][0]["mineralization"] = shallow["cells"][0]["mineralization"][:1]
        deep = deepcopy(shallow)
        deep["cells"][0]["mineralization"][0].update(from_depth_m=12, to_depth_m=14)
        shallow_model, deep_model = SurfaceModel(shallow, [analyte]), SurfaceModel(deep, [analyte])
        nearby = shallow_model.grade(5, 5, analyte)
        self.assertAlmostEqual(deep_model.grade(5, 5, analyte) / nearby, math.exp(-1))
        self.assertTrue(0 < shallow_model.grade(15, 5, analyte) < nearby)

    def test_background_ignores_hidden_identifiers_and_column_order(self):
        analytes = self.config["surface_geochemistry"]["analytes"]
        baseline = SurfaceModel(self.truth, analytes).grade(5, 5, analytes[0])
        self.truth["cells"].reverse()
        for cell in self.truth["cells"]:
            for item in cell["mineralization"]:
                item["deposit_id"] = "RENAMED"
            for item in cell["intervals"]:
                item["origin"] = "a different metadata label"
        self.assertEqual(baseline, SurfaceModel(self.truth, analytes).grade(5, 5, analytes[0]))

    def test_surface_rejects_non_soil_and_unsupported_analytes(self):
        self.config["surface_geochemistry"]["sampling_depth_to_m"] = 2
        with self.assertRaisesRegex(ValueError, "soil"):
            self.generate()
        self.config = extended_config()
        self.config["surface_geochemistry"]["analytes"][0]["analyte"] = "Diamond"
        with self.assertRaisesRegex(ValueError, "почвенной модели"):
            self.generate()

    def test_shallow_trench_observes_soil_and_does_not_copy_deeper_ore(self):
        bundle = self.generate()
        self.assertEqual(len(bundle["tables"]["trench_intervals"]), 1)
        self.assertEqual(bundle["tables"]["trench_intervals"][0]["observed_rock_id"], "soil")
        for row in bundle["tables"]["trench_samples"]:
            self.assertEqual(row["sample_material"], "soil")
            self.assertEqual(row["result_value"], 0)

    def test_trench_composites_crossed_cells_instead_of_using_midpoint(self):
        self.config["trenches"].update(depth_m=3, sample_length_m=20)
        bundle = self.generate()
        sample = bundle["tables"]["trench_samples"][0]
        self.assertAlmostEqual(sample["result_value"], .5)
        self.assertEqual(sample["sampling_depth_from_m"], 2.8)
        self.assertEqual(sample["sampling_depth_to_m"], 3)
        self.assertEqual(sample["sample_material"], "rock")

    def test_trench_stationing_reverses_consistently(self):
        self.config["trenches"].update(depth_m=3, sample_length_m=5)
        forward = [row["result_value"] for row in self.generate()["tables"]["trench_samples"]]
        path = self.config["trenches"]["paths"][0]
        path["start_x_m"], path["end_x_m"] = path["end_x_m"], path["start_x_m"]
        reverse = [row["result_value"] for row in self.generate()["tables"]["trench_samples"]]
        self.assertEqual(forward, list(reversed(reverse)))

    def test_qc_duplicates_use_same_latent_sample_despite_position_error(self):
        self.config["ideal"] = False
        self.config["noise"] = {"position_sigma_m": 20}
        self.config["quality_control"]["duplicate_every"] = 1
        bundle = self.generate()
        primary = {(row["sample_id"], row["analyte"]): row for name in ("borehole_assays", "surface_geochemistry", "trench_samples") for row in bundle["tables"][name]}
        for row in bundle["tables"]["quality_control"]:
            if row["qc_type"] == "duplicate":
                parent = primary[row["parent_sample_id"], row["analyte"]]
                self.assertEqual(row["result_value"], parent["result_value"])
                if parent["result_qualifier"] == "lt":
                    self.assertEqual(row["qc_flag"], "not_checked")
                    self.assertIsNone(row["reference_value"])
                else:
                    self.assertEqual(row["reference_value"], parent["result_value"])
                    self.assertEqual(row["qc_flag"], "pass")

    def test_standards_detect_bias_and_blanks_detect_contamination(self):
        self.config["ideal"] = False
        self.config["noise"] = {}
        self.config["quality_control"]["batch_bias_fraction"] = 1
        bundle = self.generate()
        standards = [row for row in bundle["tables"]["quality_control"] if row["qc_type"] == "standard"]
        self.assertTrue(all(row["qc_flag"] == "fail" for row in standards))
        self.assertTrue(all(row["parent_sample_id"] is None for row in standards))
        self.config["quality_control"]["batch_bias_fraction"] = -.999
        standards = [row for row in self.generate()["tables"]["quality_control"] if row["qc_type"] == "standard"]
        self.assertTrue(all(row["result_qualifier"] == "lt" and row["qc_flag"] == "fail" for row in standards))
        self.config["quality_control"].update(batch_bias_fraction=0, contamination_detection_limits=10)
        blanks = [row for row in self.generate()["tables"]["quality_control"] if row["qc_type"] == "blank"]
        self.assertTrue(all(row["qc_flag"] == "fail" for row in blanks))

    def test_ideal_controls_are_exact_and_reproducible(self):
        bundle = self.generate()
        self.assertEqual(bundle, self.generate(123))
        self.assertTrue(all(row["qc_flag"] == "pass" for row in bundle["tables"]["quality_control"]))
        self.assertTrue(all(row["qc_flag"] == "not_checked" for row in bundle["tables"]["borehole_assays"]))

    def test_disabling_methods_preserves_existing_borehole_data(self):
        baseline = generate_observations(self.truth, campaign_config(), seed=1)
        for key in ("structures", "surface_geochemistry", "trenches", "quality_control"):
            self.config[key]["enabled"] = False
        bundle = self.generate()
        for name in ("borehole_collars", "borehole_lithology", "borehole_assays", "downhole_properties"):
            self.assertEqual(baseline["tables"][name], bundle["tables"][name])
        self.assertEqual(bundle["tables"]["structural_observations"], [])
        self.assertTrue(all(not bundle["tables"][name] for name in ("surface_geochemistry", "trenches", "quality_control", "fault_intersections")))

    def test_geojson_and_csv_match_canonical_tables_without_hidden_values(self):
        bundle = self.generate()
        serialized = json.dumps(bundle)
        for forbidden in ('"deposit_id"', '"seed"', '"scene_key"', '"grades"', '"x_index"', '"trace_center_m"', '"influence_width_m"', '"vertical_displacement_m"', 'SECRET-FAULT', 'SECRET-DEPOSIT'):
            self.assertNotIn(forbidden, serialized)
        features = bundle["geojson"]["surface_geochemistry"]["features"]
        for feature, row in zip(features, bundle["tables"]["surface_geochemistry"]):
            self.assertEqual(feature["geometry"]["coordinates"], [row["x_m"], row["y_m"]])
            self.assertEqual(feature["properties"]["result_value"], row["result_value"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "surface_geochemistry.geojson"
            legacy.write_text(json.dumps(bundle["geojson"]["surface_geochemistry"]))
            save_observations(bundle, root)
            self.assertFalse(legacy.exists())
            for name, folder in (("surface_geochemistry", "surface_geochemistry"), ("trench_paths", "trenches")):
                path = root / "tables" / folder / f"{name}.geojson"
                self.assertEqual(json.loads(path.read_text()), bundle["geojson"][name])
            self.assertTrue((root / "tables/quality_control/quality_control.csv").is_file())
            self.assertTrue((root / "tables/trenches/trench_samples.csv").is_file())
            self.assertTrue((root / "tables/surface_geochemistry/surface_geochemistry.csv").is_file())

    def test_invalid_additional_plans_are_rejected(self):
        changes = [
            ("surface_geochemistry", "point_count", 0),
            ("trenches", "depth_m", 31),
            ("trenches", "sample_length_m", 0),
            ("quality_control", "duplicate_every", -1),
            ("quality_control", "batch_bias_fraction", -1),
            ("structures", "method", "unknown"),
        ]
        for section, key, value in changes:
            config = extended_config()
            if section == "surface_geochemistry":
                config[section]["layout"] = "grid"
            config[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                generate_observations(self.truth, config, seed=1)

    def test_analysis_budget_includes_controls(self):
        self.config["drilling"] = {"layout": "grid", "hole_count": 10000, "depth_m": 22, "sample_length_m": 1}
        self.config["analytes"].append({"analyte": "Fe", "unit": "% Fe", "detection_limit": .1})
        self.config["quality_control"].update(duplicate_every=1, blank_every=1, standard_every=1)
        with self.assertRaisesRegex(ValueError, "миллион"):
            self.generate()


if __name__ == "__main__":
    unittest.main()
