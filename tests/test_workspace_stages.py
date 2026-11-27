from __future__ import annotations

import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from test_observations import campaign_config, small_map
from geo_map.observations import (PRELIMINARY_TABLES, generate_observations,
                                  generate_preliminary_observations, save_preliminary_observations,
                                  save_observations)
from geo_map.workspace_server import expedition_input, serve_workspace


class WorkspaceStagesTests(unittest.TestCase):
    def setUp(self):
        self.truth = small_map()
        self.config = campaign_config()
        self.config["terrain_survey"] = {"enabled": True, "point_count": 2}
        self.config["outcrops"] = {"enabled": True, "point_count": 2}

    def test_preliminary_stage_does_not_plan_or_generate_drilling(self):
        with (patch("geo_map.observations._plan_holes") as plan,
              patch("geo_map.observations.extend_campaign") as fieldwork):
            preliminary = generate_preliminary_observations(self.truth, self.config, seed=42)
        plan.assert_not_called()
        fieldwork.assert_not_called()
        self.assertEqual(preliminary["stage"], "preliminary")
        self.assertEqual(len(preliminary["tables"]["terrain_observations"]), 2)
        self.assertTrue(all(not rows for name, rows in preliminary["tables"].items() if name not in PRELIMINARY_TABLES))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = save_preliminary_observations(preliminary, root)
            self.assertEqual(json.loads(saved.read_text()), preliminary)
            self.assertTrue((root / "tables/terrain/terrain_observations.csv").exists())
            self.assertTrue((root / "objects/terrain/TER-0001.json").exists())
            self.assertFalse((root / "tables/boreholes").exists())
            self.assertFalse((root / "objects/vertical_boreholes").exists())
            self.assertFalse((root / "sources").exists())
            self.assertFalse((root / "borehole_sources.json").exists())

    def test_fieldwork_uses_exact_preliminary_records_without_resampling(self):
        preliminary = generate_preliminary_observations(self.truth, self.config, seed=42)
        expected = generate_observations(self.truth, self.config, seed=42)
        with patch("geo_map.observations.survey_preliminary", side_effect=AssertionError("Repeated survey")):
            actual = generate_observations(self.truth, self.config, seed=42, preliminary_tables=preliminary["tables"])
        self.assertEqual(expected, actual)
        self.assertGreater(actual["summary"]["hole_count"], 0)

    def test_manual_preliminary_records_are_preserved_and_validated(self):
        preliminary = generate_preliminary_observations(self.truth, self.config, seed=42)
        payload = {name: deepcopy(preliminary["tables"][name]) for name in PRELIMINARY_TABLES}
        row = {**payload["terrain_observations"][0], "observation_id": "MANUAL-01", "surface_elevation_m": 5}
        payload["terrain_observations"].append(row)
        tables = expedition_input(self.truth, self.config, preliminary, payload)
        self.assertEqual(tables["terrain_observations"][-1], row)
        full = generate_observations(self.truth, self.config, seed=42, preliminary_tables=tables)
        self.assertIn(row, full["tables"]["terrain_observations"])
        manual_only = {name: [] for name in PRELIMINARY_TABLES}
        manual_only["terrain_observations"] = [row]
        self.assertEqual(expedition_input(self.truth, self.config, None, manual_only), manual_only)
        for invalid in ({**row, "campaign_id": "OTHER"}, {**row, "observation_id": "TER-0001"}, {**row, "x_m": -100}):
            bad = deepcopy(payload)
            bad["terrain_observations"][-1] = invalid
            with self.assertRaises(ValueError):
                expedition_input(self.truth, self.config, preliminary, bad)
        with self.assertRaises(ValueError):
            expedition_input(self.truth, self.config, None, None)

    def test_server_waits_for_each_button_and_does_not_repeat_stages(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "observations"

            def preliminary():
                calls.append("preliminary")
                result = generate_preliminary_observations(self.truth, self.config, seed=42)
                save_preliminary_observations(result, output)
                return result

            def expedition(tables):
                calls.append("expedition")
                result = generate_observations(self.truth, self.config, seed=42, preliminary_tables=tables)
                save_observations(result, output)
                (root / "recognition.json").write_text("{}")
                final = root / "final.html"
                final.write_text("done")
                return final

            def viewer(_data, path, **kwargs):
                path.write_text(json.dumps(kwargs))
                return path

            test = self

            class FakeServer:
                def __init__(self, _address, handler):
                    self.handler = handler
                    self.server_port = 9999

                def __enter__(self):
                    return self

                def __exit__(self, *_args):
                    pass

                def request(self, method, path, payload=None):
                    body = json.dumps(payload).encode() if payload is not None else b""
                    handler = object.__new__(self.handler)
                    handler.path = path
                    handler.headers = {"Content-Length": str(len(body))}
                    handler.rfile = io.BytesIO(body)
                    result = []
                    handler.send_bytes = lambda *args: result.append(args)
                    handler.send_error = lambda code: result.append((code,))
                    getattr(handler, "do_" + method)()
                    return result[0]

                def serve_forever(self):
                    initial = json.loads(self.request("GET", "/")[1])
                    test.assertEqual(calls, [])
                    test.assertFalse(output.exists())
                    collect_url, expedition_url = initial["collect_endpoint"], initial["expedition_endpoint"]
                    test.assertEqual(self.request("POST", expedition_url)[0], 400)
                    test.assertEqual(calls, [])
                    test.assertEqual(self.request("POST", collect_url)[0], 200)
                    test.assertEqual(self.request("POST", collect_url)[0], 200)
                    middle = json.loads(self.request("GET", "/")[1])
                    test.assertEqual(calls, ["preliminary"])
                    test.assertTrue(middle["preliminary_collected"])
                    test.assertFalse(middle["expedition_collected"])
                    test.assertFalse((output / "tables/boreholes").exists())
                    test.assertFalse((root / "recognition.json").exists())
                    test.assertEqual(self.request("POST", expedition_url)[0], 200)
                    test.assertEqual(self.request("POST", expedition_url)[0], 200)
                    test.assertEqual(calls, ["preliminary", "expedition"])
                    test.assertEqual(self.request("GET", "/")[1], b"done")
                    test.assertTrue((output / "tables/boreholes/borehole_collars.csv").exists())
                    test.assertTrue((root / "recognition.json").exists())

            with (patch("geo_map.workspace_server.ThreadingHTTPServer", FakeServer),
                  patch("geo_map.workspace_server.build_viewer", side_effect=viewer)):
                serve_workspace(self.truth, self.config, 42, preliminary, expedition, open_browser=False)


if __name__ == "__main__":
    unittest.main()
