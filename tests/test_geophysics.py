from __future__ import annotations

import json
import math
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from pathlib import Path

from test_observations import ROOT, campaign_config, small_map
from geo_map.boreholes import validate_trajectory
from geo_map.geophysical_observations import GEOPHYSICAL_DIRECTORIES, GEOPHYSICAL_PREFIXES, GEOPHYSICAL_TABLES, load_geophysical_csv
from geo_map.geophysics import add_geophysical_fields
from geo_map.observations import generate_observations, save_observations
from geo_map.recognition import recognize_deposits
from geo_map.recognition_spatial import survey_radius


class GeophysicsTests(unittest.TestCase):
    def setUp(self):
        self.rocks = json.loads((ROOT / "config/rocks.json").read_text())
        self.minerals = json.loads((ROOT / "config/minerals.json").read_text())
        self.config = campaign_config()
        self.config["drilling"]["holes"][1]["x_m"] = 115
        self.config["geophysical_survey"] = {"enabled": True, "point_count": 12, "magnetic_sigma_nt": 4, "gamma_sigma_cps": 2}
        self.config["analytes"] = [{"analyte": "Fe", "unit": "% Fe", "detection_limit": 0.1},
                                   {"analyte": "U₃O₈", "unit": "% U₃O₈", "detection_limit": 0.001}]

    def truth(self, uranium_top=0):
        truth = small_map()
        truth["dimensions"].update(width_m=120, width_cells=12)
        truth["rocks"] = self.rocks["rocks"]
        truth["deposits"] = [{"id": "SECRET-IRON", "mineral_id": "iron", "max_grade": 45},
                             {"id": "SECRET-URANIUM", "mineral_id": "uranium", "max_grade": 0.5}]
        iron = {"deposit_id": "SECRET-IRON", "mineral": "Fe", "grade_unit": "% Fe", "average_grade": 45,
                "from_depth_m": 10, "to_depth_m": 15}
        uranium = {"deposit_id": "SECRET-URANIUM", "mineral": "U₃O₈", "grade_unit": "% U₃O₈", "average_grade": 0.5,
                   "from_depth_m": uranium_top, "to_depth_m": uranium_top + 5}
        truth["cells"] = [{"x_index": index, "y_index": 0,
                           "intervals": [{"rock_id": "ferruginous_quartzite" if index == 0 else "sandstone",
                                          "from_depth_m": 0, "to_depth_m": 30,
                                          "properties": {"density_g_cm3": 2.5, "porosity_percent": 7}}],
                           "mineralization": [iron] if index == 0 else [uranium] if index == 11 else []} for index in range(12)]
        add_geophysical_fields(truth, {"enabled": True, "magnetic_spread_m": 5}, self.rocks["rocks"], self.minerals["minerals"])
        return truth

    def test_true_fields_attenuate_gamma_and_blur_magnetic_response(self):
        truth, buried = self.truth(), self.truth(5)
        shallow = truth["cells"][-1]["geophysical_fields"]["gamma_count_rate_cps"]
        deep = buried["cells"][-1]["geophysical_fields"]["gamma_count_rate_cps"]
        covered = self.truth(0.2)["cells"][-1]["geophysical_fields"]["gamma_count_rate_cps"]
        magnetic = [cell["geophysical_fields"]["magnetic_anomaly_nt"] for cell in truth["cells"]]
        self.assertAlmostEqual(deep, 1 + 3.36 * 1.8 + 0.586 * 2.3 + 0.265 * 12, places=4)
        self.assertAlmostEqual(shallow - deep, 0.586 * (0.5 * 8480 - 2.3), places=4)
        self.assertAlmostEqual((covered - deep) / (shallow - deep), math.exp(-100 * 2.5 * 0.045 * 0.2), places=6)
        self.assertGreater(magnetic[0], magnetic[1])
        self.assertGreater(magnetic[1], magnetic[3])
        self.assertEqual(truth["schema_version"], "2.2")

    def test_gamma_counting_uncertainty_depends_on_expected_rate(self):
        truth = self.truth()
        self.config["ideal"] = False
        self.config["geophysical_survey"].update(gamma_counting_time_s=60, gamma_sigma_cps=0.2)
        rows = generate_observations(truth, self.config, seed=1)["tables"]["gamma_observations"]
        for index in (0, 11):
            expected = truth["cells"][index]["geophysical_fields"]["gamma_count_rate_cps"]
            sigma = math.sqrt(0.2**2 + expected / 60)
            self.assertAlmostEqual(rows[index]["gamma_sigma_cps"], sigma, delta=0.00005)
        self.assertGreater(rows[-1]["gamma_sigma_cps"], rows[0]["gamma_sigma_cps"])

    def test_downhole_gamma_supports_existing_deep_assay_target(self):
        truth = self.truth(15)
        self.config["downhole_gamma"] = {"enabled": True, "interval_m": 1}
        bundle = generate_observations(truth, self.config, seed=1)
        logs = [row for row in bundle["tables"]["downhole_gamma"] if row["hole_id"] == "BH-002"]
        self.assertEqual(len(logs), 22)
        self.assertTrue(all(row["gamma_sigma_cps"] == 0 for row in logs))
        self.assertGreater(logs[15]["gamma_count_rate_cps"], logs[14]["gamma_count_rate_cps"])
        self.assertEqual(logs[15]["gamma_count_rate_cps"], logs[19]["gamma_count_rate_cps"])
        recognition = recognize_deposits(bundle, self.minerals)
        target = next(item for item in recognition["targets"] if item["mineral_id"] == "uranium")
        self.assertIn("downhole_gamma_anomaly", target["supporting_signals"])
        self.assertNotIn("geophysics_gamma", target["supporting_signals"])
        self.assertIn(logs[15]["measurement_id"], target["downhole_gamma_evidence"]["measurement_ids"])
        bundle["tables"]["downhole_gamma"] = []
        target = next(item for item in recognize_deposits(bundle, self.minerals)["targets"] if item["mineral_id"] == "uranium")
        self.assertNotIn("downhole_gamma_anomaly", target["supporting_signals"])

    def test_recomputing_saved_fields_uses_current_rock_calibration(self):
        truth = self.truth(5)
        index = 4
        old_rate = truth["cells"][index]["geophysical_fields"]["gamma_count_rate_cps"]
        catalog = deepcopy(self.rocks["rocks"])
        sandstone = next(rock for rock in catalog if rock["id"] == "sandstone")
        sandstone["geophysical_source"]["potassium_percent"] += 1
        settings = {"enabled": True, "magnetic_spread_m": 5}
        add_geophysical_fields(truth, settings, catalog, self.minerals["minerals"])
        self.assertEqual(truth["cells"][index]["geophysical_fields"]["gamma_count_rate_cps"], old_rate)
        add_geophysical_fields(truth, settings, catalog, self.minerals["minerals"], replace=True)
        self.assertAlmostEqual(truth["cells"][index]["geophysical_fields"]["gamma_count_rate_cps"], old_rate + 3.36)

    def test_survey_measures_and_exports_without_truth_parameters(self):
        truth = self.truth()
        bundle = generate_observations(truth, self.config, seed=1)
        magnetic, gamma = (bundle["tables"][table] for table in GEOPHYSICAL_TABLES.values())
        self.assertEqual(len(magnetic), 12)
        self.assertEqual(len(gamma), 12)
        self.assertEqual(magnetic[0]["station_id"], gamma[0]["station_id"])
        self.assertNotEqual(magnetic[0]["observation_id"], gamma[0]["observation_id"])
        self.assertNotIn("gamma_count_rate_cps", magnetic[0])
        self.assertNotIn("magnetic_anomaly_nt", gamma[0])
        self.assertEqual(magnetic[0]["magnetic_anomaly_nt"], truth["cells"][0]["geophysical_fields"]["magnetic_anomaly_nt"])
        self.assertEqual(magnetic[0]["magnetic_sigma_nt"], 0)
        self.config["ideal"] = False
        measured = generate_observations(truth, self.config, seed=1)["tables"]["gamma_observations"]
        self.assertEqual(measured[0]["gamma_sigma_cps"], 2)
        self.assertNotEqual(measured[0]["gamma_count_rate_cps"], gamma[0]["gamma_count_rate_cps"])
        text = json.dumps(bundle)
        for key in ("geophysical_fields", "geophysical_source", "magnetic_decay_m", "SECRET-URANIUM"):
            self.assertNotIn(key, text)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy_path = root / "tables/geophysics/geophysical_observations.csv"
            legacy_path.parent.mkdir(parents=True)
            legacy_path.touch()
            save_observations(bundle, root)
            self.assertFalse(legacy_path.exists())
            for method, table in GEOPHYSICAL_TABLES.items():
                directory = GEOPHYSICAL_DIRECTORIES[table]
                path = root / "tables" / directory / f"{table}.csv"
                template = ROOT / "templates/observations" / path.name
                self.assertEqual(path.read_text().splitlines()[0], template.read_text().splitlines()[0])
                self.assertEqual(load_geophysical_csv(path, method, self.config["campaign_id"]), bundle["tables"][table])
                feature = json.loads(path.with_suffix(".geojson").read_text())["features"][0]
                self.assertEqual(feature["geometry"]["coordinates"], [5, 5])
                record = json.loads((root / "objects" / directory / f"{GEOPHYSICAL_PREFIXES[method]}-0001.json").read_text())
                self.assertEqual(record["tables"], {table: bundle["tables"][table][:1]})

    def test_both_channels_support_separate_targets_without_promoting_unassayed_anomalies(self):
        bundle = generate_observations(self.truth(), self.config, seed=1)
        result = recognize_deposits(bundle, self.minerals)
        targets = {target["mineral_id"]: target for target in result["targets"]}
        self.assertIn("geophysics_magnetic", targets["iron"]["supporting_signals"])
        self.assertIn("geophysics_gamma", targets["uranium"]["supporting_signals"])
        self.assertEqual(result["summary"]["targets_supported_by_geophysics"], 2)
        self.assertGreaterEqual(result["summary"]["geophysical_anomaly_count"], 2)
        self.assertTrue(targets["iron"]["geophysical_evidence"]["observation_id"].startswith("MAG-"))
        self.assertTrue(targets["uranium"]["geophysical_evidence"]["observation_id"].startswith("GAM-"))
        gamma = bundle["tables"].pop("gamma_observations")
        magnetic_only = recognize_deposits(bundle, self.minerals)
        self.assertEqual({row["method"] for row in magnetic_only["geophysical_anomalies"]}, {"magnetic"})
        bundle["tables"]["gamma_observations"] = gamma
        bundle["tables"]["borehole_assays"] = []
        result = recognize_deposits(bundle, self.minerals)
        self.assertEqual(result["targets"], [])
        self.assertTrue(result["geophysical_anomalies"])

    def test_hybrid_drilling_uses_measured_anomalies_and_preserves_random_coverage(self):
        truth = self.truth()
        self.config["drilling"] = {
            "layout": "random", "hole_count": 10, "random_fraction": 0.4, "depth_m": 10, "sample_length_m": 5,
            "orientations": [{"dip_deg": -90}, {"dip_deg": -60, "azimuth_deg": 90}, {"dip_deg": -60, "azimuth_deg": 270}],
        }
        random_plan = generate_observations(truth, self.config, seed=2)
        self.config["drilling"]["layout"] = "hybrid"
        hybrid = generate_observations(truth, self.config, seed=2)
        self.assertEqual(hybrid, generate_observations(truth, self.config, seed=2))
        wells = hybrid["tables"]["borehole_collars"]
        self.assertEqual(len(wells), 10)
        self.assertEqual(wells[:4], random_plan["tables"]["borehole_collars"][:4])
        channels = {method: hybrid["tables"][table] for method, table in GEOPHYSICAL_TABLES.items()}
        for method, table in GEOPHYSICAL_TABLES.items():
            self.assertEqual(channels[method], random_plan["tables"][table])
        by_channel = {method: {row["observation_id"]: row for row in rows} for method, rows in channels.items()}
        targets = hybrid["drilling_targets"]
        self.assertEqual({target["method"] for target in targets.values()}, {"magnetic", "gamma"})
        self.assertGreater(max(Counter(target["observation_id"] for target in targets.values()).values()), 1)
        radius = 1.5 * survey_radius(truth["dimensions"], len(channels["magnetic"]))
        for well in wells:
            validate_trajectory({**well, "depth_m": well["total_depth_m"]}, truth["dimensions"])
            if target := targets.get(well["hole_id"]):
                reading = by_channel[target["method"]][target["observation_id"]]
                distance = math.dist((well["x_m"], well["y_m"]), (reading["x_m"], reading["y_m"]))
                self.assertLessEqual(distance, radius + 1e-6)

    def test_hybrid_drilling_falls_back_to_random_without_usable_anomalies(self):
        truth = self.truth()
        for cell in truth["cells"]:
            cell["geophysical_fields"] = {"magnetic_anomaly_nt": 0, "gamma_count_rate_cps": 20}
        self.config["drilling"].update(layout="random", hole_count=10)
        baseline = generate_observations(truth, self.config, seed=2)["tables"]["borehole_collars"]
        self.config["drilling"]["layout"] = "hybrid"
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                self.config["geophysical_survey"]["enabled"] = enabled
                hybrid = generate_observations(truth, self.config, seed=2)
                self.assertEqual(hybrid["drilling_targets"], {})
                self.assertEqual(hybrid["tables"]["borehole_collars"], baseline)

    def test_deep_uranium_remains_an_assay_target_with_no_surface_gamma_support(self):
        bundle = generate_observations(self.truth(5), self.config, seed=1)
        # An unrelated high surface reading above the hole must not corroborate its deep assay.
        bundle["tables"]["gamma_observations"][-1]["gamma_count_rate_cps"] = 400
        result = recognize_deposits(bundle, self.minerals)
        uranium = next(target for target in result["targets"] if target["mineral_id"] == "uranium")
        self.assertEqual(uranium["from_m"], 5)
        self.assertNotIn("geophysics_gamma", uranium["supporting_signals"])
        self.assertTrue(any(row["method"] == "gamma" for row in result["geophysical_anomalies"]))


if __name__ == "__main__":
    unittest.main()
