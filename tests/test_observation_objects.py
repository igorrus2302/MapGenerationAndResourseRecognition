from __future__ import annotations

import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from test_observation_models import extended_config, extended_map
from geo_map.observations import generate_observations, save_observations


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ObservationObjectTests(unittest.TestCase):
    def test_individual_files_partition_records_and_link_children(self):
        config = extended_config()
        config["analytes"].append({"analyte": "Fe", "unit": "% Fe", "detection_limit": .01})
        config["drilling"]["holes"][1].update(azimuth_deg=270, dip_deg=-60)
        bundle = generate_observations(extended_map(), config, seed=1)
        with tempfile.TemporaryDirectory() as temp:
            root = save_observations(bundle, temp).parent / "objects"
            manifest = read_json(root / "index.json")
            records = defaultdict(list)
            for kind, entries in manifest["objects"].items():
                if kind not in {"outcrop_observations", "terrain_observations", "geophysical_observations"}:
                    self.assertTrue(entries, kind)
                for identifier, path in entries.items():
                    item = read_json(root / path)
                    self.assertEqual((item["kind"], item["object_id"]), (kind, identifier))
                    self.assertEqual(item["campaign_id"], config["campaign_id"])
                    for name, rows in item["tables"].items():
                        records[name].extend(rows)
            self.assertEqual(records.keys(), {name for name, rows in bundle["tables"].items() if rows})
            for name, rows in bundle["tables"].items():
                self.assertCountEqual(records[name], rows, name)

            vertical = "vertical_boreholes/BH-001"
            inclined = "inclined_boreholes/BH-002"
            self.assertEqual(manifest["objects"]["boreholes"], {
                "BH-001": f"{vertical}/BH-001.json", "BH-002": f"{inclined}/BH-002.json",
            })
            hole = read_json(root / f"{vertical}/BH-001.json")
            self.assertEqual(len(hole["sample_files"]), 5)
            for path in hole["sample_files"]:
                self.assertEqual(Path(path).parent.as_posix(), f"{vertical}/samples")
                sample = read_json(root / path)["tables"]
                assays = sample["borehole_assays"]
                self.assertEqual({row["analyte"] for row in assays}, {"Cu", "Fe"})
                self.assertEqual({row["hole_id"] for row in assays}, {"BH-001"})
                properties = sample["downhole_properties"][0]
                self.assertEqual((properties["hole_id"], properties["from_m"], properties["to_m"]),
                                 ("BH-001", assays[0]["from_m"], assays[0]["to_m"]))
            fault_path = f"{vertical}/structures/BH-001-F001.json"
            self.assertIn(fault_path, hole["structural_files"])
            fault = read_json(root / fault_path)
            self.assertEqual(set(fault["tables"]), {"structural_observations", "fault_intersections"})
            inclined_hole = read_json(root / f"{inclined}/BH-002.json")
            self.assertEqual(inclined_hole["sample_files"], [f"{inclined}/samples/BH-002-S{i:04d}.json" for i in range(1, 6)])
            trench = read_json(root / "trenches/TR-001/TR-001.json")
            self.assertEqual(trench["sample_files"], [f"trenches/TR-001/samples/TR-001-S{i:04d}.json" for i in range(1, 5)])
            self.assertEqual(manifest["objects"]["surface_samples"]["SG-001"], "surface_geochemistry/SG-001.json")
            self.assertEqual({Path(path).parent.as_posix() for path in manifest["objects"]["quality_control_samples"].values()},
                             {"quality_control/duplicates", "quality_control/blanks", "quality_control/standards"})

    def test_regeneration_removes_disappearing_objects(self):
        truth, config = extended_map(), extended_config()
        with tempfile.TemporaryDirectory() as temp:
            root = save_observations(generate_observations(truth, config, seed=1), temp).parent / "objects"
            self.assertTrue((root / "surface_geochemistry/SG-001.json").is_file())
            self.assertTrue((root / "vertical_boreholes/BH-002/BH-002.json").is_file())
            config["surface_geochemistry"]["enabled"] = False
            config["drilling"]["holes"].pop()
            config["drilling"]["holes"][0].update(azimuth_deg=90, dip_deg=-60)
            save_observations(generate_observations(truth, config, seed=1), temp)
            self.assertEqual(list((root / "surface_geochemistry").iterdir()), [])
            self.assertEqual(list((root / "vertical_boreholes").iterdir()), [])
            objects = read_json(root / "index.json")["objects"]
            self.assertEqual(objects["boreholes"], {"BH-001": "inclined_boreholes/BH-001/BH-001.json"})
            self.assertEqual(objects["surface_samples"], {})

    def test_manual_identifiers_cannot_escape_or_overwrite_files(self):
        truth, config = extended_map(), extended_config()
        holes = config["drilling"]["holes"]
        holes[1]["hole_id"] = "bh-001"
        holes.append({**holes[0], "hole_id": "../../скважина"})
        with tempfile.TemporaryDirectory() as temp:
            root = save_observations(generate_observations(truth, config, seed=1), temp).parent / "objects"
            paths = read_json(root / "index.json")["objects"]["boreholes"]
            self.assertEqual(len({path.casefold() for path in paths.values()}), 3)
            for identifier, path in paths.items():
                file = root / path
                self.assertEqual(file.resolve().parent.parent, (root / "vertical_boreholes").resolve())
                self.assertEqual(read_json(file)["object_id"], identifier)
