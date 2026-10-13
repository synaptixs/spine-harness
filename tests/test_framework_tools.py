"""Offline checks for framework version resolution; no tools are installed by tests."""

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from spineharness import framework_tools


class FrameworkToolTests(unittest.TestCase):
    def test_latest_spec_kit_prefers_highest_stable_tag_and_peeled_commit(self):
        rows = "\n".join(
            [
                f"{'a' * 40}\trefs/tags/v1.1.3",
                f"{'b' * 40}\trefs/tags/v1.1.3^{{}}",
                f"{'c' * 40}\trefs/tags/v1.2.0-beta.1",
                f"{'d' * 40}\trefs/tags/v1.0.11",
            ]
        )
        with patch.object(framework_tools, "command", return_value=rows):
            self.assertEqual(framework_tools.latest_spec_kit(), ("v1.1.3", "b" * 40))

    def test_setup_installs_latest_but_records_exact_versions(self):
        with patch.object(framework_tools, "latest_spec_kit", return_value=("v1.1.3", "b" * 40)):
            with patch.object(framework_tools, "command", side_effect=["Spec Kit 1.1.3", "", "1.15.0"]) as run:
                resolved = framework_tools.setup()
        self.assertEqual(resolved["speckit_ref"], "git+https://github.com/github/spec-kit.git@" + "b" * 40)
        self.assertEqual(resolved["openspec_version"], "1.15.0")
        self.assertEqual(run.call_args_list[0].args[0][:3], ["uvx", "--refresh", "--from"])
        self.assertEqual(run.call_args_list[1].args[0], ["npm", "install", "--global", "@fission-ai/openspec@latest"])

    def test_config_setup_freezes_versions_before_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "matrix.json"
            config.write_text(json.dumps({
                "name": "issue-1", "source_repo": str(root / "source"),
                "task_file": str(root / "issue.json"), "frameworks": ["speckit", "openspec"],
                "model": "gpt-6-sol", "login_home": str(root / "login"),
                "work_dir": str(root / "work"), "results_dir": str(root / "results"),
            }))
            resolved = {"speckit_tag": "v1.1.3", "speckit_ref": "git+https://github.com/github/spec-kit.git@" + "b" * 40,
                        "openspec_version": "1.15.0"}
            with patch.object(framework_tools, "setup", return_value=resolved), patch.object(
                sys, "argv", ["framework_tools", "--config", str(config)]
            ), redirect_stdout(io.StringIO()):
                framework_tools.main()
            self.assertEqual(json.loads(config.read_text())["speckit_ref"], resolved["speckit_ref"])
            from spineharness.framework_matrix import load

            self.assertEqual(load(config)["openspec_version"], "1.15.0")

    def test_existing_manifest_is_reused_without_updating_versions(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / "framework-tools.json"
            manifest.write_text(json.dumps({"speckit_ref": "pinned", "openspec_version": "1.15.0"}))
            with patch.object(framework_tools, "setup") as setup, patch.object(
                framework_tools, "command", return_value="1.15.0"
            ), patch.object(sys, "argv", ["framework_tools", "--manifest", str(manifest)]), redirect_stdout(io.StringIO()):
                framework_tools.main()
            setup.assert_not_called()


if __name__ == "__main__":
    unittest.main()
