from __future__ import annotations

import json
import math
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from test_observations import ROOT, campaign_config, small_map
from geo_map.boreholes import validate_trajectory
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
        magnetic = [cell["geophysical_fields"]["magnetic_anomaly_nt"] for cell in truth["cells"]]
        self.assertGreater(shallow - deep, 800)
        self.assertAlmostEqual(deep, 21, places=2)
        self.assertGreater(magnetic[0], magnetic[1])
        self.assertGreater(magnetic[1], magnetic[3])
        self.assertEqual(truth["schema_version"], "2.2")

    def test_survey_measures_and_exports_without_truth_parameters(self):
        truth = self.truth()
        bundle = generate_observations(truth, self.config, seed=1)
        rows = bundle["tables"]["geophysical_observations"]
        self.assertEqual(len(rows), 12)
        self.assertEqual(rows[0]["magnetic_anomaly_nt"], truth["cells"][0]["geophysical_fields"]["magnetic_anomaly_nt"])
        self.assertEqual(rows[0]["magnetic_sigma_nt"], 0)
        self.config["ideal"] = False
        measured = generate_observations(truth, self.config, seed=1)["tables"]["geophysical_observations"]
        self.assertEqual(measured[0]["gamma_sigma_cps"], 2)
        self.assertNotEqual(measured[0]["gamma_count_rate_cps"], rows[0]["gamma_count_rate_cps"])
        text = json.dumps(bundle)
        for key in ("geophysical_fields", "geophysical_source", "magnetic_decay_m", "SECRET-URANIUM"):
            self.assertNotIn(key, text)
        with tempfile.TemporaryDirectory() as folder:
            root = save_observations(bundle, folder).parent
            feature = json.loads((root / "tables/geophysics/geophysical_observations.geojson").read_text())["features"][0]
            self.assertEqual(feature["geometry"]["coordinates"], [5, 5])
            record = json.loads((root / "objects/geophysics/GEO-0001.json").read_text())
            self.assertEqual(record["tables"]["geophysical_observations"], rows[:1])

    def test_both_channels_support_separate_targets_without_promoting_unassayed_anomalies(self):
        bundle = generate_observations(self.truth(), self.config, seed=1)
        result = recognize_deposits(bundle, self.minerals)
        targets = {target["mineral_id"]: target for target in result["targets"]}
        self.assertIn("geophysics_magnetic", targets["iron"]["supporting_signals"])
        self.assertIn("geophysics_gamma", targets["uranium"]["supporting_signals"])
        self.assertEqual(result["summary"]["targets_supported_by_geophysics"], 2)
        self.assertGreaterEqual(result["summary"]["geophysical_anomaly_count"], 2)
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
        rows = hybrid["tables"]["geophysical_observations"]
        self.assertEqual(rows, random_plan["tables"]["geophysical_observations"])
        by_id = {row["observation_id"]: row for row in rows}
        targets = hybrid["drilling_targets"]
        self.assertEqual({target["method"] for target in targets.values()}, {"magnetic", "gamma"})
        self.assertGreater(max(Counter(target["observation_id"] for target in targets.values()).values()), 1)
        radius = 1.5 * survey_radius(truth["dimensions"], len(rows))
        for well in wells:
            validate_trajectory({**well, "depth_m": well["total_depth_m"]}, truth["dimensions"])
            if target := targets.get(well["hole_id"]):
                reading = by_id[target["observation_id"]]
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
        bundle["tables"]["geophysical_observations"][-1]["gamma_count_rate_cps"] = 400
        result = recognize_deposits(bundle, self.minerals)
        uranium = next(target for target in result["targets"] if target["mineral_id"] == "uranium")
        self.assertEqual(uranium["from_m"], 5)
        self.assertNotIn("geophysics_gamma", uranium["supporting_signals"])
        self.assertTrue(any(row["method"] == "gamma" for row in result["geophysical_anomalies"]))


if __name__ == "__main__":
    unittest.main()
