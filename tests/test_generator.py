from __future__ import annotations

import json
import sys
import tempfile
import unittest
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
            self.assertEqual(loaded["schema_version"], "1.1")
            self.assertIn("Горизонтальный срез", html)
            self.assertIn("vertical-x", html)
            self.assertIn("const presentRocks", html)
            self.assertIn("Порода-носитель", html)
            self.assertIn("slicePositionM", html)
            self.assertIn("depthM: Math.min(5", html)
            self.assertIn('"map_kind":"synthetic_ground_truth"', html)


if __name__ == "__main__":
    unittest.main()
