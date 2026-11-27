from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main


class RunOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.output = self.root / "map"
        self.output.mkdir()
        self.truth = {"schema_version": "2.2", "map_kind": "synthetic_ground_truth",
                      "geophysics": {}, "seed": 123}
        self.old_files = ("observations/objects/terrain/TER-0001.json",
                          "observations/observations.json", "internal/expedition_run.json",
                          "recognition.json", "reconstructed_map.json", "map_view.html")
        for name in self.old_files:
            path = self.output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("old", encoding="utf-8")
        (self.output / "map.json").write_text(json.dumps(self.truth), encoding="utf-8")
        self.unrelated = self.output / "notes.txt"
        self.unrelated.write_text("keep", encoding="utf-8")
        self.archive = self.root / "map_archive" / "observations.json"
        self.archive.parent.mkdir()
        self.archive.write_text("archived", encoding="utf-8")

    def assert_clean(self, expected_truth: dict) -> None:
        self.assertFalse((self.output / "observations").exists())
        self.assertFalse((self.output / "internal").exists())
        for name in self.old_files:
            self.assertFalse((self.output / name).exists(), name)
        self.assertEqual(json.loads((self.output / "map.json").read_text()), expected_truth)
        self.assertEqual(self.unrelated.read_text(), "keep")
        self.assertEqual(self.archive.read_text(), "archived")

    def test_restart_cleans_output_before_interactive_workspace(self) -> None:
        new_truth = {**self.truth, "seed": 456}

        def serve(data, *_args, **_kwargs):
            self.assertEqual(data, new_truth)
            self.assert_clean(new_truth)

        with (patch.object(sys, "argv", ["main.py", "--output", str(self.output), "--no-browser"]),
              patch.object(main, "generate_map", return_value=new_truth),
              patch.object(main, "generate_observations") as generate_observations,
              patch.object(main, "serve_workspace", side_effect=serve) as server):
            main.main()
        server.assert_called_once()
        generate_observations.assert_not_called()

    def test_restart_using_current_map_preserves_loaded_truth(self) -> None:
        def serve(data, *_args, **_kwargs):
            self.assertEqual(data, self.truth)
            self.assert_clean(self.truth)

        with (patch.object(sys, "argv", ["main.py", "--map", str(self.output / "map.json"),
                                        "--output", str(self.output), "--no-browser"]),
              patch.object(main, "serve_workspace", side_effect=serve) as server):
            main.main()
        server.assert_called_once()

    def test_batch_restart_also_cleans_before_collection(self) -> None:
        def collect(data, output, *_args, **kwargs):
            self.assertEqual(output, self.output)
            self.assertFalse(kwargs["preliminary_collected"])
            self.assert_clean(data)
            return output / "map_view.html"

        with (patch.object(sys, "argv", ["main.py", "--map", str(self.output / "map.json"),
                                        "--output", str(self.output), "--batch"]),
              patch.object(main, "run_expedition", side_effect=collect) as expedition):
            main.main()
        expedition.assert_called_once()

    def test_external_symlink_target_is_not_removed(self) -> None:
        import shutil
        shutil.rmtree(self.output / "observations")
        (self.output / "observations").symlink_to(self.archive.parent, target_is_directory=True)
        main.prepare_run_output(self.truth, self.output)
        self.assert_clean(self.truth)

    def test_input_file_in_cleanup_directory_is_protected(self) -> None:
        source = self.output / "observations" / "input_map.json"
        source.write_text(json.dumps(self.truth), encoding="utf-8")
        with self.assertRaises(ValueError):
            main.prepare_run_output(self.truth, self.output, input_paths=(source,))
        self.assertTrue(source.exists())
        self.assertTrue((self.output / "recognition.json").exists())


if __name__ == "__main__":
    unittest.main()
