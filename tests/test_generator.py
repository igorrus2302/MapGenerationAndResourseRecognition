from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from geo_map.generator import generate_map, load_config, save_map
from geo_map.viewer import build_viewer


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(
            ROOT / "config/generation.json",
            ROOT / "config/rocks.json",
            ROOT / "config/minerals.json",
        )
        cls.generated = generate_map(cls.config, seed=123)

    def test_same_seed_produces_same_geology(self) -> None:
        repeated = generate_map(self.config, seed=123)
        self.assertEqual(self.generated["cells"], repeated["cells"])
        self.assertEqual(self.generated["statistics"], repeated["statistics"])

    def test_seed_is_random_when_not_provided(self) -> None:
        with patch("geo_map.generator.secrets.randbits", side_effect=[111, 222]):
            first = generate_map(self.config)
            second = generate_map(self.config)
        self.assertEqual(first["seed"], 111)
        self.assertEqual(second["seed"], 222)
        self.assertNotEqual(first["cells"], second["cells"])

    def test_intervals_cover_every_column_without_gaps(self) -> None:
        total_depth = self.generated["dimensions"]["depth_m"]
        for cell in self.generated["cells"]:
            intervals = cell["intervals"]
            self.assertEqual(intervals[0]["from_depth_m"], 0)
            self.assertEqual(intervals[-1]["to_depth_m"], total_depth)
            for left, right in zip(intervals, intervals[1:]):
                self.assertEqual(left["to_depth_m"], right["from_depth_m"])
                self.assertLess(left["from_depth_m"], left["to_depth_m"])

    def test_stratigraphic_groups_always_follow_shallow_to_deep_order(self) -> None:
        configured_groups = self.config["geology"]["stratigraphic_groups"]
        group_order = {"surface": 0}
        group_order.update(
            {group["id"]: index + 1 for index, group in enumerate(configured_groups)}
        )
        required_groups = {
            group["id"] for group in configured_groups if group["minimum_layers"] > 0
        }

        for seed in range(20):
            generated = generate_map(self.config, seed=seed)
            layer_groups = [
                layer["stratigraphic_group"]
                for layer in generated["geological_layers"]
            ]
            ranks = [group_order[group_id] for group_id in layer_groups]
            self.assertEqual(ranks, sorted(ranks))
            self.assertTrue(required_groups <= set(layer_groups))

    def test_map_contains_mineralized_cells(self) -> None:
        count = sum(bool(cell["mineralization"]) for cell in self.generated["cells"])
        self.assertGreater(count, 0)
        self.assertEqual(count, self.generated["statistics"]["mineralized_cell_count"])

    def test_layers_and_deposits_are_generated_from_seed(self) -> None:
        other = generate_map(self.config, seed=124)
        self.assertNotEqual(
            self.generated["geological_layers"], other["geological_layers"]
        )
        self.assertNotEqual(self.generated["deposits"], other["deposits"])
        self.assertTrue(
            all(deposit["origin"] == "generated" for deposit in self.generated["deposits"])
        )

    def test_generated_deposits_have_distinct_minerals(self) -> None:
        mineral_ids = [deposit["mineral_id"] for deposit in self.generated["deposits"]]
        self.assertGreaterEqual(len(mineral_ids), 2)
        self.assertEqual(len(mineral_ids), len(set(mineral_ids)))

    def test_deposits_stay_inside_mineral_depth_ranges(self) -> None:
        config = deepcopy(self.config)
        mineral_count = len(config["minerals"])
        config["deposit_generation"]["count"] = [mineral_count, mineral_count]
        generated = generate_map(config, seed=321)

        self.assertEqual(len(generated["deposits"]), mineral_count)
        for deposit in generated["deposits"]:
            depth_low, depth_high = deposit["allowed_depth_m"]
            center_depth = deposit["center_m"][2]
            radius_depth = deposit["radii_m"][2]
            self.assertGreaterEqual(center_depth - radius_depth, depth_low)
            self.assertLessEqual(center_depth + radius_depth, depth_high)

    def test_deposit_shapes_are_irregular_and_asymmetric(self) -> None:
        deposits_by_id = {
            deposit["id"]: deposit for deposit in self.generated["deposits"]
        }
        self.assertTrue(
            all(deposit["shape"]["irregularity"] > 0 for deposit in deposits_by_id.values())
        )

        asymmetric_intervals = 0
        for cell in self.generated["cells"]:
            for mineralization in cell["mineralization"]:
                deposit = deposits_by_id[mineralization["deposit_id"]]
                center_depth = deposit["center_m"][2]
                top_extent = center_depth - mineralization["from_depth_m"]
                bottom_extent = mineralization["to_depth_m"] - center_depth
                if abs(top_extent - bottom_extent) > 0.05:
                    asymmetric_intervals += 1
        self.assertGreater(asymmetric_intervals, 0)

    def test_rocks_file_is_only_a_catalogue(self) -> None:
        source = json.loads((ROOT / "config/rocks.json").read_text(encoding="utf-8"))
        self.assertEqual(set(source), {"rocks"})
        self.assertNotIn("map", source)
        self.assertNotIn("deposit", source)

    def test_minerals_file_is_only_a_catalogue(self) -> None:
        source = json.loads((ROOT / "config/minerals.json").read_text(encoding="utf-8"))
        self.assertEqual(set(source), {"minerals"})
        mineral_ids = {mineral["id"] for mineral in source["minerals"]}
        generated_ids = {
            deposit["id"].split("_deposit_")[0]
            for deposit in self.generated["deposits"]
        }
        self.assertTrue(generated_ids <= mineral_ids)

    def test_chunks_are_not_persisted(self) -> None:
        self.assertNotIn("chunks", self.generated)
        self.assertTrue(all("chunk" not in cell for cell in self.generated["cells"]))

    def test_json_and_viewer_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            json_path = save_map(self.generated, directory_path / "map.json")
            html_path = build_viewer(self.generated, directory_path / "map_view.html")
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            html = html_path.read_text(encoding="utf-8")
            self.assertEqual(loaded["schema_version"], "1.2")
            self.assertIn("Разрез по оси Z", html)
            self.assertIn("vertical-x", html)
            self.assertIn("const presentRocks", html)
            self.assertIn("Порода-носитель", html)
            self.assertIn("slicePositionM", html)
            self.assertIn("depthM: Math.min(5", html)
            self.assertIn("const VIEW_STEP_M = 1", html)
            self.assertIn("Точка 1 × 1 м", html)
            self.assertIn("усиленные линии — 50 м", html)
            self.assertIn('"map_kind":"synthetic_ground_truth"', html)


if __name__ == "__main__":
    unittest.main()
