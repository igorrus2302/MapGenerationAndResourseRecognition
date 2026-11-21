from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from geo_map.observations import TABLE_FIELDS, TruthSampler, generate_observations, save_observations
from geo_map.viewer import build_viewer


def small_map() -> dict:
    intervals = [
        {"from_depth_m": 0, "to_depth_m": 10, "rock_id": "a", "properties": {"density_g_cm3": 2, "porosity_percent": 20}},
        {"from_depth_m": 10, "to_depth_m": 30, "rock_id": "b", "properties": {"density_g_cm3": 4, "porosity_percent": 2}},
    ]
    return {
        "schema_version": "2.0", "map_kind": "synthetic_ground_truth", "seed": 987654321,
        "dimensions": {"width_cells": 2, "height_cells": 1, "depth_cells": 3, "cell_size_m": 10, "depth_step_m": 10, "width_m": 20, "height_m": 10, "depth_m": 30},
        "rocks": [{"id": "a", "name": "Песчаник", "category": "sedimentary", "color": "#d8b46a"}, {"id": "b", "name": "Базальт", "category": "volcanic", "color": "#4b4a4f"}],
        "deposits": [{"id": "SECRET-DEPOSIT", "max_grade": 12345}],
        "statistics": {"cell_count": 2, "mineralized_cell_count": 1},
        "cells": [
            {"x_index": 0, "y_index": 0, "intervals": deepcopy(intervals), "mineralization": [
                {"from_depth_m": 2, "to_depth_m": 4, "mineral": "Cu", "average_grade": 1, "grade_unit": "% Cu", "deposit_id": "SECRET-DEPOSIT"},
                {"from_depth_m": 12, "to_depth_m": 13, "mineral": "Cu", "average_grade": 2, "grade_unit": "% Cu", "deposit_id": "SECRET-DEPOSIT"},
            ]},
            {"x_index": 1, "y_index": 0, "intervals": deepcopy(intervals), "mineralization": []},
        ],
    }


def campaign_config() -> dict:
    return {
        "campaign_id": "TEST-EXP", "title": "Тестовая экспедиция", "date": "2026-10-22", "ideal": True,
        "drilling": {"layout": "manual", "depth_m": 22, "sample_length_m": 5,
                     "holes": [{"hole_id": "BH-001", "x_m": 5, "y_m": 5}, {"hole_id": "BH-002", "x_m": 15, "y_m": 5}]},
        "noise": {"position_sigma_m": 1.5, "boundary_sigma_m": 1, "density_sigma_g_cm3": .02, "porosity_sigma_percent": .3,
                  "assay_relative_sigma": .05, "assay_detection_limit_sigma_fraction": .15,
                  "missing_sample_probability": .1, "lithology_error_probability": .1},
        "analytes": [{"analyte": "Cu", "unit": "% Cu", "detection_limit": .01}],
    }


class ObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.truth = small_map()
        self.config = campaign_config()

    def test_sample_is_diluted_by_whole_interval_not_midpoint(self) -> None:
        sample = TruthSampler(self.truth).sample(5, 5, 0, 10, self.config["analytes"])
        self.assertAlmostEqual(sample["grades"]["Cu"], .2)

    def test_sample_is_mass_weighted_across_rock_boundaries(self) -> None:
        sample = TruthSampler(self.truth).sample(5, 5, 0, 15, self.config["analytes"])
        self.assertAlmostEqual(sample["grades"]["Cu"], .3)
        self.assertAlmostEqual(sample["density_g_cm3"], 40 / 15)
        self.assertAlmostEqual(sample["porosity_percent"], 14)

    def test_interval_edges_are_half_open_and_thin_intersections_are_preserved(self) -> None:
        sampler = TruthSampler(self.truth)
        self.assertEqual(sampler.sample(5, 5, 4, 10, self.config["analytes"])["grades"]["Cu"], 0)
        self.assertEqual(sampler.sample(5, 5, 2, 4, self.config["analytes"])["grades"]["Cu"], 1)
        self.assertAlmostEqual(sampler.sample(5, 5, 10, 15, self.config["analytes"])["grades"]["Cu"], .4)
        self.assertEqual(sampler.sample(10, 5, 0, 10, self.config["analytes"])["grades"]["Cu"], 0)

    def test_observation_seed_is_reproducible_and_independent(self) -> None:
        self.config["ideal"] = False
        first = generate_observations(self.truth, self.config, seed=41)
        self.assertEqual(first, generate_observations(self.truth, self.config, seed=41))
        self.assertNotEqual(first, generate_observations(self.truth, self.config, seed=42))
        self.assertEqual(self.truth, small_map())
        self.assertEqual(self.config["noise"]["position_sigma_m"], 1.5)

    def test_ideal_mode_has_no_noise_or_missing_samples(self) -> None:
        bundle = generate_observations(self.truth, self.config, seed=1)
        self.assertEqual(bundle, generate_observations(self.truth, self.config, seed=2))
        self.assertEqual(bundle["summary"]["sample_count"], 10)
        self.assertEqual(bundle["summary"]["missing_sample_count"], 0)
        self.assertEqual(bundle["tables"]["borehole_collars"][0]["x_m"], 5)
        first_assay = bundle["tables"]["borehole_assays"][0]
        self.assertAlmostEqual(first_assay["result_value"], .4)
        self.assertIsNone(first_assay["result_qualifier"])
        self.assertEqual(bundle["tables"]["borehole_assays"][4]["to_m"], 22)

    def test_detection_limit_censors_results_and_does_not_claim_qc_pass(self) -> None:
        self.config["ideal"] = False
        self.config["noise"] = {}
        bundle = generate_observations(self.truth, self.config, seed=4)
        barren = next(row for row in bundle["tables"]["borehole_assays"] if row["hole_id"] == "BH-002")
        self.assertEqual(barren["result_value"], .01)
        self.assertEqual(barren["result_qualifier"], "lt")
        self.assertEqual(barren["qc_flag"], "not_checked")

    def test_decimal_steps_and_precise_end_depth_do_not_create_invalid_samples(self) -> None:
        for depth, step, expected_count in ((2.1, .3, 7), (22.1234567, 5, 5)):
            config = deepcopy(self.config)
            config["drilling"]["depth_m"] = depth
            config["drilling"]["sample_length_m"] = step
            bundle = generate_observations(self.truth, config, seed=1)
            rows = [row for row in bundle["tables"]["borehole_assays"] if row["hole_id"] == "BH-001"]
            self.assertEqual(len(rows), expected_count)
            self.assertEqual(rows[-1]["to_m"], depth)
            for left, right in zip(rows, rows[1:]):
                self.assertEqual(left["to_m"], right["from_m"])
            self.assertTrue(all(row["from_m"] < row["to_m"] <= depth for row in rows))

    def test_all_missing_samples_preserve_collars_and_logs(self) -> None:
        self.config["ideal"] = False
        self.config["noise"]["missing_sample_probability"] = 1
        bundle = generate_observations(self.truth, self.config, seed=4)
        self.assertEqual(bundle["summary"]["sample_count"], 0)
        self.assertEqual(bundle["summary"]["missing_sample_count"], 10)
        self.assertEqual(bundle["tables"]["borehole_assays"], [])
        self.assertEqual(bundle["tables"]["downhole_properties"], [])
        self.assertEqual(len(bundle["tables"]["borehole_lithology"]), 4)

    def test_public_records_have_no_hidden_truth_fields(self) -> None:
        bundle = generate_observations(self.truth, self.config, seed=4)
        forbidden = {"seed", "deposit_id", "intrusive_deposit_id", "center_m", "radii_m", "max_grade", "maximum_grade", "average_grade", "display_threshold", "shape", "geological_model", "geological_control", "x_index", "y_index", "inside_deposit", "is_anomaly", "controlling_fault_id", "origin"}
        def check(value):
            if isinstance(value, dict):
                self.assertFalse(value.keys() & forbidden)
                for child in value.values():
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
        check(bundle)
        serialized = json.dumps(bundle)
        self.assertNotIn("SECRET-DEPOSIT", serialized)
        self.assertNotIn("987654321", serialized)
        for name, rows in bundle["tables"].items():
            for row in rows:
                self.assertEqual(set(row), set(TABLE_FIELDS[name]))

    def test_journals_cover_drilled_depth_without_gaps_even_with_large_errors(self) -> None:
        self.config["ideal"] = False
        self.config["noise"]["boundary_sigma_m"] = 1000
        bundle = generate_observations(self.truth, self.config, seed=5)
        for collar in bundle["tables"]["borehole_collars"]:
            logs = [row for row in bundle["tables"]["borehole_lithology"] if row["hole_id"] == collar["hole_id"]]
            self.assertEqual(logs[0]["from_m"], 0)
            self.assertEqual(logs[-1]["to_m"], collar["total_depth_m"])
            for row in logs:
                self.assertLess(row["from_m"], row["to_m"])
            for left, right in zip(logs, logs[1:]):
                self.assertEqual(left["to_m"], right["from_m"])

    def test_planning_does_not_depend_on_deposits(self) -> None:
        self.config["drilling"] = {"layout": "random", "hole_count": 7, "depth_m": 20, "sample_length_m": 5}
        first = generate_observations(self.truth, self.config, seed=9)
        changed = deepcopy(self.truth)
        changed["deposits"] = []
        changed["cells"][0]["mineralization"] = []
        changed["seed"] = 123
        second = generate_observations(changed, self.config, seed=9)
        self.assertEqual(first["tables"]["borehole_collars"], second["tables"]["borehole_collars"])
        self.assertEqual(first["plan"], second["plan"])

    def test_invalid_plans_probabilities_and_units_are_rejected(self) -> None:
        for key, value in (("depth_m", 31), ("sample_length_m", 0)):
            config = deepcopy(self.config)
            config["drilling"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                generate_observations(self.truth, config, seed=1)
        for coordinate in (-1, 20, float("nan")):
            config = deepcopy(self.config)
            config["drilling"]["holes"][0]["x_m"] = coordinate
            with self.subTest(x=coordinate), self.assertRaises(ValueError):
                generate_observations(self.truth, config, seed=1)
        config = deepcopy(self.config)
        config["noise"]["missing_sample_probability"] = 1.5
        with self.assertRaises(ValueError):
            generate_observations(self.truth, config, seed=1)
        config = deepcopy(self.config)
        config["analytes"][0]["unit"] = "g/t Cu"
        with self.assertRaisesRegex(ValueError, "единицы"):
            generate_observations(self.truth, config, seed=1)

    def test_csv_export_matches_templates_and_public_json(self) -> None:
        bundle = generate_observations(self.truth, self.config, seed=7)
        with tempfile.TemporaryDirectory() as directory:
            path = save_observations(bundle, directory)
            self.assertEqual(json.loads(path.read_text()), bundle)
            tables_dir = Path(directory) / "tables"
            for name, rows in bundle["tables"].items():
                csv_file, = tables_dir.glob(f"*/{name}.csv")
                with csv_file.open(encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream)
                    exported = list(reader)
                    self.assertEqual(reader.fieldnames, TABLE_FIELDS[name])
                    self.assertEqual(len(exported), len(rows))
                template = ROOT / "templates/observations" / f"{name}.csv"
                if template.exists():
                    self.assertEqual(template.read_text().splitlines()[0].split(","), TABLE_FIELDS[name])
            with (tables_dir / "boreholes/structural_observations.csv").open(encoding="utf-8") as stream:
                self.assertEqual(next(csv.DictReader(stream))["strike_deg"], "")

    def test_viewer_has_four_tabs_and_safe_embedded_observations(self) -> None:
        self.config["title"] = '</script><script>alert(1)</script> __MAP_DATA__'
        bundle = generate_observations(self.truth, self.config, seed=7)
        with tempfile.TemporaryDirectory() as directory:
            html = build_viewer(self.truth, Path(directory) / "viewer.html", observations=bundle).read_text()
            for panel in ("truthPanel", "expeditionPanel", "recognizedPanel", "similarityPanel"):
                self.assertIn(f'id="{panel}"', html)
            self.assertIn("Результаты поиска ещё не загружены", html)
            self.assertNotIn('<script>alert(1)</script>', html)
            literal = html.split("const OBSERVATION_DATA = ", 1)[1].split(";\n", 1)[0]
            self.assertEqual(json.loads(literal), bundle)
            self.assertEqual(html.count("</script>"), 1)


if __name__ == "__main__":
    unittest.main()
