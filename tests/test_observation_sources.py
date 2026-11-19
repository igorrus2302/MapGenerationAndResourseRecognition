from __future__ import annotations

import csv
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from test_observations import ROOT, campaign_config, small_map
from geo_map.observation_sources import BOREHOLE_SOURCE_TABLES, make_borehole_source
from geo_map.observations import TABLE_FIELDS, generate_observations, save_observations


class BoreholeSourceTests(unittest.TestCase):
    def setUp(self):
        self.truth, self.config = small_map(), campaign_config()
        self.config["drilling"].update(depth_m=16)
        self.config["drilling"]["holes"][1].update(azimuth_deg=270, dip_deg=-60)
        self.truth["faults"] = [{"trace_center_m": [0, 5], "strike_deg": 0, "dip_deg": 45, "influence_width_m": 1}]
        self.config["structures"] = {"enabled": True, "observe_faults": True}
        self.bundle = generate_observations(self.truth, self.config, seed=12)

    def test_sources_partition_all_borehole_observations_without_duplicates(self):
        sources = self.bundle["borehole_sources"]
        self.assertEqual([source["kind"] for source in sources], ["vertical_boreholes", "inclined_boreholes"])
        self.assertNotEqual(sources[0]["source_id"], sources[1]["source_id"])
        self.assertEqual(sources[0]["hole_ids"], ["BH-001"])
        self.assertEqual(sources[1]["hole_ids"], ["BH-002"])
        packs = [make_borehole_source(self.bundle, source["kind"]) for source in sources]
        for name in BOREHOLE_SOURCE_TABLES:
            combined = [row for pack in packs for row in pack["tables"][name]]
            key = lambda row: json.dumps(row, sort_keys=True)
            self.assertEqual(sorted(map(key, combined)), sorted(map(key, self.bundle["tables"][name])))
        for source, pack in zip(sources, packs):
            self.assertEqual(pack["source"], source)
            self.assertEqual(pack["summary"]["hole_count"], 1)
            self.assertEqual(pack["summary"]["drilled_m"], 16)
            self.assertEqual(pack["summary"]["assay_count"], len(pack["tables"]["borehole_assays"]))
            for rows in pack["tables"].values():
                self.assertTrue(all(row["hole_id"] in source["hole_ids"] for row in rows))

    def test_source_is_standalone_and_has_no_other_source_or_hidden_truth(self):
        for kind, other_hole in (("vertical_boreholes", "BH-002"), ("inclined_boreholes", "BH-001")):
            pack = make_borehole_source(self.bundle, kind)
            text = json.dumps(pack)
            self.assertNotIn(other_hole, text)
            for forbidden in ("SECRET-DEPOSIT", '"seed"', '"x_index"', '"deposit_id"', '"trace_center_m"'):
                self.assertNotIn(forbidden, text)
            catalog = {rock["id"] for rock in pack["rock_catalog"]}
            self.assertTrue(all(row["observed_rock_id"] in catalog for row in pack["tables"]["borehole_lithology"]))
            self.assertEqual(set(pack["tables"]), set(BOREHOLE_SOURCE_TABLES))
            self.assertNotIn("quality_control", pack["tables"])

    def test_source_export_has_matching_csv_json_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            save_observations(self.bundle, directory)
            manifest = json.loads((directory / "borehole_sources.json").read_text())
            self.assertEqual(manifest["borehole_sources"], self.bundle["borehole_sources"])
            self.assertEqual(len(list(directory.glob("*.csv"))), 11)
            for source in manifest["borehole_sources"]:
                folder = directory / source["directory"]
                pack = json.loads((folder / "observations.json").read_text())
                self.assertEqual(pack, make_borehole_source(self.bundle, source["kind"]))
                for name in BOREHOLE_SOURCE_TABLES:
                    with (folder / f"{name}.csv").open(newline='', encoding='utf-8') as stream:
                        reader = csv.DictReader(stream)
                        rows = list(reader)
                        self.assertEqual(reader.fieldnames, pack["table_fields"][name])
                        self.assertEqual(len(rows), len(pack["tables"][name]))
                        for row, expected in zip(rows, pack["tables"][name]):
                            self.assertEqual(row, {key: '' if value is None else str(value) for key, value in expected.items()})

    def test_saving_vertical_only_replaces_previous_inclined_data_with_empty_source(self):
        with tempfile.TemporaryDirectory() as temp:
            save_observations(self.bundle, temp)
            vertical = generate_observations(small_map(), campaign_config(), seed=12)
            save_observations(vertical, temp)
            folder = Path(temp) / "sources/inclined_boreholes"
            pack = json.loads((folder / "observations.json").read_text())
            self.assertEqual(pack["summary"]["hole_count"], 0)
            self.assertTrue(all(not rows for rows in pack["tables"].values()))
            for file in folder.glob('*.csv'):
                with file.open(newline='', encoding='utf-8') as stream:
                    self.assertEqual(list(csv.DictReader(stream)), [])

    def test_all_missing_samples_keep_source_collars_and_logs(self):
        self.config["ideal"] = False
        self.config["noise"] = {"missing_sample_probability": 1}
        bundle = generate_observations(self.truth, self.config, seed=12)
        for source in bundle["borehole_sources"]:
            pack = make_borehole_source(bundle, source["kind"])
            self.assertEqual(pack["summary"]["sample_count"], 0)
            self.assertTrue(pack["tables"]["borehole_collars"])
            self.assertTrue(pack["tables"]["borehole_lithology"])

    def test_source_edits_do_not_change_combined_observations(self):
        before = deepcopy(self.bundle)
        pack = make_borehole_source(self.bundle, "inclined_boreholes")
        pack["tables"]["borehole_collars"][0]["x_m"] = -100
        pack["source"]["hole_ids"].clear()
        pack["plan"]["analytes"].clear()
        self.assertEqual(self.bundle, before)
        with self.assertRaises(ValueError):
            make_borehole_source(self.bundle, 'unknown')

    def test_both_source_templates_have_matching_records_and_valid_links(self):
        for kind in ("vertical_boreholes", "inclined_boreholes"):
            folder = ROOT / 'templates/observations/sources' / kind
            pack = json.loads((folder / 'observations.json').read_text())
            self.assertEqual(pack["source"]["kind"], kind)
            holes = {row["hole_id"]: row for row in pack["tables"]["borehole_collars"]}
            for hole in holes.values():
                self.assertEqual(hole["dip_deg"] == -90, kind == 'vertical_boreholes')
            for name in BOREHOLE_SOURCE_TABLES:
                with (folder / f'{name}.csv').open(newline='', encoding='utf-8') as stream:
                    reader = csv.DictReader(stream)
                    rows = list(reader)
                    self.assertEqual(reader.fieldnames, TABLE_FIELDS[name])
                    self.assertEqual(len(rows), len(pack['tables'][name]))
                    for csv_row, row in zip(rows, pack['tables'][name]):
                        self.assertEqual(csv_row, {key: '' if value is None else str(value) for key, value in row.items()})
                        self.assertIn(row['hole_id'], holes)
                        if 'from_m' in row and row['from_m'] is not None:
                            self.assertTrue(0 <= row['from_m'] < row['to_m'] <= holes[row['hole_id']]['total_depth_m'])


if __name__ == '__main__':
    unittest.main()
