from __future__ import annotations

import math
import unittest
from copy import deepcopy

from test_observations import campaign_config, small_map
from geo_map.boreholes import point
from geo_map.observations import generate_observations


class InclinedBoreholeTests(unittest.TestCase):
    def setUp(self):
        self.truth, self.config = small_map(), campaign_config()
        self.config["drilling"].update(depth_m=16, sample_length_m=16, holes=[
            {"hole_id": "ANGLED", "x_m": 5, "y_m": 5, "azimuth_deg": 90, "dip_deg": -30},
        ])

    def generate(self, seed=1):
        return generate_observations(self.truth, self.config, seed=seed)

    def test_samples_follow_crossed_columns_and_thin_ore_with_mass_weighting(self):
        # A crosses into B at 10/sqrt(3) metres along the core, not at its midpoint.
        for index, cell in enumerate(self.truth["cells"]):
            cell["intervals"] = [{"from_depth_m": 0, "to_depth_m": 30, "rock_id": "ab"[index],
                                  "properties": {"density_g_cm3": 2 + 2 * index, "porosity_percent": 20 - 18 * index}}]
            cell["mineralization"] = [{"from_depth_m": 1 if index == 0 else 7,
                                       "to_depth_m": 2 if index == 0 else 7.5,
                                       "mineral": "Cu", "average_grade": 1 if index == 0 else 3,
                                       "grade_unit": "% Cu", "deposit_id": "SECRET-DEPOSIT"}]
        bundle = self.generate()
        crossing = 10 / math.sqrt(3)
        mass = 2 * crossing + 4 * (16 - crossing)
        self.assertAlmostEqual(bundle["tables"]["borehole_assays"][0]["result_value"], 16 / mass, places=7)
        properties = bundle["tables"]["downhole_properties"][0]
        self.assertAlmostEqual(properties["density_g_cm3"], mass / 16, places=6)
        self.assertAlmostEqual(properties["porosity_percent"], (20 * crossing + 2 * (16 - crossing)) / 16, places=6)
        logs = bundle["tables"]["borehole_lithology"]
        self.assertEqual([row["observed_rock_id"] for row in logs], ["a", "b"])
        self.assertAlmostEqual(logs[0]["to_m"], crossing, places=6)
        self.assertEqual(logs[1]["from_m"], logs[0]["to_m"])
        self.assertEqual(logs[-1]["to_m"], 16)
        self.assertEqual(bundle["tables"]["borehole_collars"][0]["dip_deg"], -30)
        self.assertEqual(bundle["summary"]["inclined_hole_count"], 1)
        self.assertEqual(bundle["plan"]["borehole_depth_reference"], "measured_depth_m")

    def test_layer_contacts_are_measured_along_core_and_same_rock_cells_merge(self):
        self.config["drilling"]["depth_m"] = 22
        self.config["drilling"]["holes"][0]["dip_deg"] = -60
        bundle = self.generate()
        logs = bundle["tables"]["borehole_lithology"]
        self.assertEqual(len(logs), 2)
        self.assertAlmostEqual(logs[0]["to_m"], 20 / math.sqrt(3), places=6)
        contact = bundle["tables"]["structural_observations"][0]
        self.assertEqual(contact["depth_m"], logs[0]["to_m"])
        self.assertEqual(logs[-1]["to_m"], 22)

    def test_core_length_can_exceed_model_vertical_depth(self):
        self.truth["dimensions"]["depth_m"] = 10
        for cell in self.truth["cells"]:
            cell["intervals"] = [cell["intervals"][0]]
            cell["mineralization"] = []
        bundle = self.generate()
        self.assertEqual(bundle["summary"]["drilled_m"], 16)
        hole = {**self.config["drilling"]["holes"][0], "depth_m": 16}
        self.assertAlmostEqual(point(hole, 16)[2], 8)

    def test_thin_lithology_intervals_keep_positive_length_even_with_boundary_noise(self):
        self.config["ideal"] = False
        self.config["noise"] = {"boundary_sigma_m": 1000}
        self.config["drilling"]["holes"][0]["dip_deg"] = -60
        for cell in self.truth["cells"]:
            cell["mineralization"] = []
            cell["intervals"] = [
                {"from_depth_m": start, "to_depth_m": end, "rock_id": rock,
                 "properties": {"density_g_cm3": 2, "porosity_percent": 10}}
                for start, end, rock in ((0, 10, "a"), (10, 10.0000001, "b"), (10.0000001, 30, "a"))
            ]
        logs = self.generate()["tables"]["borehole_lithology"]
        self.assertEqual([row["observed_rock_id"] for row in logs], ["a", "b", "a"])
        self.assertTrue(all(row["from_m"] < row["to_m"] for row in logs))
        self.assertEqual(logs[0]["to_m"], logs[1]["from_m"])
        self.assertEqual(logs[1]["to_m"], logs[2]["from_m"])

    def test_diagonal_crossing_at_a_cell_corner_does_not_create_false_intervals(self):
        self.truth["dimensions"].update(height_cells=2, height_m=20)
        self.truth["rocks"].append({"id": "ghost", "name": "Не пересекается", "category": "sedimentary", "color": "#aaaaaa"})
        self.config["drilling"].update(depth_m=20)
        for azimuth, sx, sy in ((45, 0, 0), (135, 0, 1), (225, 1, 1), (315, 1, 0)):
            for dip in (-10, -30, -45, -60):
                with self.subTest(azimuth=azimuth, dip=dip):
                    self.truth["cells"] = []
                    for x in range(2):
                        for y in range(2):
                            rock = "a" if (x, y) == (sx, sy) else "b" if (x, y) == (1-sx, 1-sy) else "ghost"
                            self.truth["cells"].append({"x_index": x, "y_index": y, "mineralization": [],
                                "intervals": [{"from_depth_m": 0, "to_depth_m": 30, "rock_id": rock,
                                               "properties": {"density_g_cm3": 2, "porosity_percent": 10}}]})
                    self.config["drilling"]["holes"][0].update(x_m=sx*10+5, y_m=sy*10+5, azimuth_deg=azimuth, dip_deg=dip)
                    logs = self.generate()["tables"]["borehole_lithology"]
                    self.assertEqual([row["observed_rock_id"] for row in logs], ["a", "b"])
                    self.assertAlmostEqual(logs[0]["to_m"], 5 * math.sqrt(2) / math.cos(math.radians(dip)))
                    self.assertTrue(all(row["from_m"] < row["to_m"] for row in logs))

    def test_inclined_hole_crosses_a_fault_missed_by_vertical_hole_at_same_collar(self):
        self.truth["faults"] = [{"trace_center_m": [0, 5], "strike_deg": 0, "dip_deg": 90, "influence_width_m": 1}]
        self.config["structures"] = {"enabled": True, "observe_faults": True, "method": "oriented_core"}
        self.config["drilling"]["holes"] = [
            {"hole_id": "ANGLED", "x_m": 5, "y_m": 1, "azimuth_deg": 0, "dip_deg": -60},
            {"hole_id": "VERTICAL", "x_m": 5, "y_m": 1},
        ]
        rows = self.generate()["tables"]["fault_intersections"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["hole_id"], "ANGLED")
        self.assertAlmostEqual(rows[0]["from_m"], 6)
        self.assertAlmostEqual(rows[0]["to_m"], 10)

    def test_holes_parallel_to_a_dipping_fault_can_be_inside_or_outside(self):
        self.truth["faults"] = [{"trace_center_m": [0, 1], "strike_deg": 0, "dip_deg": 60, "influence_width_m": .5}]
        self.config["structures"] = {"enabled": True, "observe_faults": True}
        self.config["drilling"]["holes"] = [
            {"hole_id": "INSIDE", "x_m": 5, "y_m": 1, "azimuth_deg": 0, "dip_deg": -60},
            {"hole_id": "OUTSIDE", "x_m": 5, "y_m": 2, "azimuth_deg": 0, "dip_deg": -60},
        ]
        rows = self.generate()["tables"]["fault_intersections"]
        self.assertEqual([(row["hole_id"], row["from_m"], row["to_m"]) for row in rows], [("INSIDE", 0, 16)])

    def test_automatic_mixed_plans_fit_map_and_do_not_depend_on_ore(self):
        for layout in ("grid", "random"):
            self.config["drilling"] = {"layout": layout, "hole_count": 7, "depth_m": 16, "sample_length_m": 5,
                "orientations": [{"dip_deg": -90}, {"dip_deg": -60, "azimuth_deg": 90}, {"dip_deg": -30, "azimuth_deg": 270}]}
            first = self.generate(seed=99)
            self.assertEqual(first, self.generate(seed=99))
            self.assertEqual(first["summary"]["vertical_hole_count"], 3)
            self.assertEqual(first["summary"]["inclined_hole_count"], 4)
            for hole in first["tables"]["borehole_collars"]:
                x, y, z = point(hole, hole["total_depth_m"])
                self.assertTrue(0 <= x <= 20 and 0 <= y <= 10 and 0 <= z <= 30)
            changed = deepcopy(self.truth)
            changed["cells"][0]["mineralization"] = []
            second = generate_observations(changed, self.config, seed=99)
            self.assertEqual(first["tables"]["borehole_collars"], second["tables"]["borehole_collars"])

    def test_invalid_angles_and_trajectories_are_rejected(self):
        for key, value in (("dip_deg", 0), ("dip_deg", -91), ("dip_deg", float("nan")), ("dip_deg", True),
                           ("azimuth_deg", -1), ("azimuth_deg", 360), ("azimuth_deg", "90"), ("azimuth_deg", float("inf"))):
            config = deepcopy(self.config)
            config["drilling"]["holes"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                generate_observations(self.truth, config, seed=1)
        for changes in ({"x_m": 19}, {"x_m": 1, "azimuth_deg": 270}, {"dip_deg": -90, "depth_m": 31}):
            config = deepcopy(self.config)
            config["drilling"]["holes"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "границы"):
                generate_observations(self.truth, config, seed=1)
        for pattern in ([], [False], [{"dip_deg": 1}], [{"dip_deg": -1, "azimuth_deg": 0}]):
            config = deepcopy(self.config)
            config["drilling"].update(layout="grid", hole_count=1, orientations=pattern)
            with self.subTest(pattern=pattern), self.assertRaises(ValueError):
                generate_observations(self.truth, config, seed=1)

    def test_terminal_boundary_is_allowed_and_old_plans_remain_vertical(self):
        hole = self.config["drilling"]["holes"][0]
        hole.update(x_m=12, azimuth_deg=90, dip_deg=-60)
        self.generate()  # 16 m at -60 degrees ends exactly on X=20.
        old = generate_observations(small_map(), campaign_config(), seed=1)
        self.assertEqual(old["summary"]["vertical_hole_count"], 2)
        self.assertEqual(old["summary"]["inclined_hole_count"], 0)
        for row in old["tables"]["borehole_collars"]:
            self.assertEqual((row["azimuth_deg"], row["dip_deg"]), (0, -90))


if __name__ == "__main__":
    unittest.main()
