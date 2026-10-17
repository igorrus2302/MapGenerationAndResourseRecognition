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

from geo_map.generator import (
    _fault_signed_distance_m,
    _rotated_horizontal_extents,
    generate_map,
    load_config,
    save_map,
)
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

    def test_configured_layer_thickness_limits_are_preserved(self) -> None:
        config = deepcopy(self.config)
        config["deposit_generation"]["count"] = [0, 0]
        surface_low, surface_high = config["geology"]["surface_thickness_m"]
        minimum_thickness = config["geology"]["minimum_layer_thickness_m"]

        for seed in range(5):
            generated = generate_map(config, seed=seed)
            for cell in generated["cells"]:
                intervals = cell["intervals"]
                surface_thickness = intervals[0]["to_depth_m"]
                self.assertGreaterEqual(surface_thickness, surface_low)
                self.assertLessEqual(surface_thickness, surface_high)
                for interval in intervals[1:]:
                    self.assertGreaterEqual(
                        interval["to_depth_m"] - interval["from_depth_m"],
                        minimum_thickness,
                    )

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
        count_low, count_high = self.config["deposit_generation"]["count"]
        for seed in range(10):
            generated = generate_map(self.config, seed=seed)
            width_m = generated["dimensions"]["width_m"]
            height_m = generated["dimensions"]["height_m"]
            self.assertGreaterEqual(len(generated["deposits"]), count_low)
            self.assertLessEqual(len(generated["deposits"]), count_high)
            for deposit in generated["deposits"]:
                depth_low, depth_high = deposit["allowed_depth_m"]
                center_x, center_y, center_depth = deposit["center_m"]
                radius_x, radius_y, radius_depth = deposit["radii_m"]
                extent_x, extent_y = _rotated_horizontal_extents(
                    radius_x,
                    radius_y,
                    deposit["shape"]["rotation_deg"],
                )
                self.assertGreaterEqual(center_x - extent_x, 0)
                self.assertLessEqual(center_x + extent_x, width_m)
                self.assertGreaterEqual(center_y - extent_y, 0)
                self.assertLessEqual(center_y + extent_y, height_m)
                self.assertGreaterEqual(center_depth - radius_depth, depth_low)
                self.assertLessEqual(center_depth + radius_depth, depth_high)

    def test_deposits_and_segments_are_bound_to_actual_rocks(self) -> None:
        cell_size = self.generated["dimensions"]["cell_size_m"]
        deposits_by_id = {
            deposit["id"]: deposit for deposit in self.generated["deposits"]
        }
        materialized_ids: set[str] = set()

        for deposit in self.generated["deposits"]:
            center_x, center_y, center_z = deposit["center_m"]
            x_index = min(
                self.generated["dimensions"]["width_cells"] - 1,
                int(center_x // cell_size),
            )
            y_index = min(
                self.generated["dimensions"]["height_cells"] - 1,
                int(center_y // cell_size),
            )
            cell = self.generated["cells"][
                y_index * self.generated["dimensions"]["width_cells"] + x_index
            ]
            interval = next(
                item
                for item in cell["intervals"]
                if item["from_depth_m"] <= center_z < item["to_depth_m"]
            )
            self.assertEqual(interval["rock_id"], deposit["center_host_rock_id"])

        for cell in self.generated["cells"]:
            for item in cell["mineralization"]:
                materialized_ids.add(item["deposit_id"])
                deposit = deposits_by_id[item["deposit_id"]]
                self.assertIn(
                    item["host_rock_id"],
                    deposit["permitted_mineralized_rock_ids"],
                )
                matching = [
                    interval
                    for interval in cell["intervals"]
                    if interval["rock_id"] == item["host_rock_id"]
                    and interval["from_depth_m"] <= item["from_depth_m"]
                    and item["to_depth_m"] <= interval["to_depth_m"]
                ]
                self.assertTrue(matching)
                self.assertEqual(item["grade_unit"], deposit["grade_unit"])
                self.assertLess(item["from_depth_m"], item["to_depth_m"])
                self.assertGreater(item["maximum_grade"], 0)
                self.assertLessEqual(item["maximum_grade"], deposit["max_grade"])

        self.assertEqual(materialized_ids, set(deposits_by_id))

    def test_center_host_is_unambiguous_on_layer_boundaries(self) -> None:
        generated = generate_map(self.config, seed=407)
        width_cells = generated["dimensions"]["width_cells"]
        cell_size = generated["dimensions"]["cell_size_m"]
        for deposit in generated["deposits"]:
            center_x, center_y, center_z = deposit["center_m"]
            x_index = int(center_x // cell_size)
            y_index = int(center_y // cell_size)
            cell = generated["cells"][y_index * width_cells + x_index]
            matching = [
                interval
                for interval in cell["intervals"]
                if interval["from_depth_m"] <= center_z < interval["to_depth_m"]
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["rock_id"], deposit["center_host_rock_id"])

    def test_rounding_never_creates_zero_length_intervals(self) -> None:
        generated = generate_map(self.config, seed=21)
        for cell in generated["cells"]:
            for interval in cell["intervals"]:
                self.assertLess(interval["from_depth_m"], interval["to_depth_m"])
            for item in cell["mineralization"]:
                self.assertLess(item["from_depth_m"], item["to_depth_m"])

    def test_fault_control_references_generated_fault(self) -> None:
        fault_ids = {fault["id"] for fault in self.generated["faults"]}
        for deposit in self.generated["deposits"]:
            if deposit["geological_model"]["control"] == "fault":
                self.assertIn(deposit["controlling_fault_id"], fault_ids)

    def test_fault_control_follows_the_dipping_fault_plane(self) -> None:
        config = deepcopy(self.config)
        gold = next(item for item in config["minerals"] if item["id"] == "gold")
        config["minerals"] = [gold]
        config["deposit_generation"]["count"] = [1, 1]
        generated = generate_map(config, seed=0)
        deposit = generated["deposits"][0]
        faults_by_id = {fault["id"]: fault for fault in generated["faults"]}
        fault = faults_by_id[deposit["controlling_fault_id"]]
        self.assertIn("dip_direction_deg", fault)

        segments = [
            (cell, item)
            for cell in generated["cells"]
            for item in cell["mineralization"]
        ]
        self.assertTrue(segments)
        cell_size = generated["dimensions"]["cell_size_m"]
        for cell, item in segments:
            x_m = cell["x_m"] + cell_size / 2
            y_m = cell["y_m"] + cell_size / 2
            depth_m = (item["from_depth_m"] + item["to_depth_m"]) / 2
            self.assertLessEqual(
                abs(_fault_signed_distance_m(fault, x_m, y_m, depth_m)),
                fault["influence_width_m"] + 0.02,
            )

    def test_intrusive_model_replaces_country_rock(self) -> None:
        generated = generate_map(self.config, seed=0)
        intrusive = [
            deposit
            for deposit in generated["deposits"]
            if deposit["geological_model"]["control"] == "intrusive"
        ]
        self.assertTrue(intrusive)
        for deposit in intrusive:
            self.assertEqual(
                deposit["center_host_rock_id"],
                deposit["geological_model"]["body_rock_id"],
            )
            self.assertIsNotNone(deposit["country_host_rock_id"])
            segments = [
                item
                for cell in generated["cells"]
                for item in cell["mineralization"]
                if item["deposit_id"] == deposit["id"]
            ]
            self.assertTrue(segments)
            self.assertTrue(all("country_rock_ids" in item for item in segments))

    def test_contact_model_uses_a_real_layer_boundary(self) -> None:
        config = deepcopy(self.config)
        emerald = next(item for item in config["minerals"] if item["id"] == "emerald")
        config["minerals"] = [emerald]
        config["deposit_generation"]["count"] = [1, 1]
        config["geology"]["layer_count"] = [3, 3]
        config["geology"]["stratigraphic_groups"] = [
            {
                "id": "intrusive_contact",
                "name": "Гранитный контакт",
                "minimum_layers": 1,
                "rock_ids": ["granite"],
            },
            {
                "id": "metamorphic_host",
                "name": "Метаморфическая порода",
                "minimum_layers": 1,
                "rock_ids": ["schist"],
            },
        ]
        generated = generate_map(config, seed=41)
        deposit = generated["deposits"][0]
        self.assertEqual(deposit["geological_model"]["control"], "contact")
        self.assertEqual(set(deposit["contact_pair_rock_ids"]), {"granite", "schist"})
        self.assertLessEqual(
            abs(deposit["center_m"][2] - deposit["contact_depth_m"]),
            0.02,
        )

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

    def test_catalogues_include_new_geological_models(self) -> None:
        rock_ids = {rock["id"] for rock in self.config["rocks"]}
        active_rock_ids = {
            rock_id
            for group in self.config["geology"]["stratigraphic_groups"]
            for rock_id in group["rock_ids"]
        }
        self.assertTrue(
            {
                "conglomerate", "siltstone", "claystone", "shale",
                "carbonaceous_shale", "dolomite", "chert", "dacite", "rhyolite",
                "granodiorite", "gabbro", "peridotite", "slate", "schist",
                "gneiss", "quartzite", "marble", "amphibolite", "serpentinite",
                "ferruginous_quartzite",
            }
            <= active_rock_ids
        )
        self.assertTrue({"kimberlite", "pegmatite", "carbonatite"} <= rock_ids)
        self.assertFalse({"kimberlite", "pegmatite", "carbonatite"} & active_rock_ids)
        mineral_ids = {mineral["id"] for mineral in self.config["minerals"]}
        self.assertTrue(
            {
                "lead_zinc", "nickel_copper", "chromite", "tin_tungsten",
                "lithium", "copper_zinc_vms", "phosphorite", "manganese",
                "rare_earth",
            }
            <= mineral_ids
        )

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
            self.assertEqual(loaded["schema_version"], "2.0")
            self.assertIn("faults", loaded)
            self.assertIn("Разрез по оси Z", html)
            self.assertIn("vertical-x", html)
            self.assertIn("const presentRocks", html)
            self.assertIn("Порода-носитель", html)
            self.assertIn("for (const interval of cell.intervals)", html)
            self.assertIn("mineral.from_depth_m * geometry.cellSize", html)
            self.assertIn("slicePositionM", html)
            self.assertIn("depthM: Math.min(5", html)
            self.assertIn("const VIEW_STEP_M = 1", html)
            self.assertIn("Точка 1 × 1 м", html)
            self.assertIn("усиленные линии — 50 м", html)
            self.assertIn("mineral.grade_unit", html)
            self.assertIn('"schema_version":"2.0"', html)
            self.assertIn('"map_kind":"synthetic_ground_truth"', html)


if __name__ == "__main__":
    unittest.main()
