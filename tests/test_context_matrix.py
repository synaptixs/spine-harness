"""Offline protocol checks; no Codex or framework process is started."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spineharness import context_matrix
from spineharness.framework_matrix import codex_environment


def command(*args: str, cwd: Path) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


class ContextMatrixTest(unittest.TestCase):
    def setUp(self) -> None:
        version_patch = patch.object(context_matrix, "codex_version", return_value="codex-cli test")
        version_patch.start()
        self.addCleanup(version_patch.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="context-matrix-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        command("git", "init", "-q", str(self.source), cwd=self.root)
        command("git", "config", "user.email", "test@example.invalid", cwd=self.source)
        command("git", "config", "user.name", "Test", cwd=self.source)
        (self.source / "value.txt").write_text("bad\n")
        (self.source / "test_acceptance.py").write_text(
            "from pathlib import Path\nassert Path('value.txt').read_text() == 'good\\n'\n"
        )
        command("git", "add", ".", cwd=self.source)
        command("git", "commit", "-qm", "baseline", cwd=self.source)
        baseline = command("git", "rev-parse", "HEAD", cwd=self.source)
        (self.source / "value.txt").write_text("good\n")
        fix = self.root / "fix.patch"
        fix.write_text(command("git", "diff", "--", "value.txt", cwd=self.source) + "\n")
        command("git", "checkout", "--", "value.txt", cwd=self.source)
        task = self.root / "task.json"
        task.write_text(json.dumps({"id": "TEST-1", "title": "Fix value", "description": "Set value to good."}))
        contexts = {}
        for arm in context_matrix.ARMS:
            path = self.root / f"{arm}.json"
            path.write_text(json.dumps({"arm": arm, "task_id": "TEST-1", "baseline_commit": baseline,
                                        "producer": arm, "readiness": "approved", "text": f"Context from {arm}."}))
            contexts[arm] = str(path)
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({
            "name": "fixture", "source_repo": str(self.source), "baseline": baseline,
            "task_file": str(task), "contexts": contexts, "model": "gpt-6-sol",
            "login_home": str(self.root / "login"), "application_python": sys.executable,
            "checks": [["{python}", "-c", "from pathlib import Path; assert Path('value.txt').exists()"]],
            "acceptance_checks": [["{python}", "test_acceptance.py"]],
            "known_fix_patch": str(fix), "results_dir": str(self.root / "results"),
            "work_dir": str(self.root / "work"),
        }))

    @staticmethod
    def offline_checks(repo: Path, commands: list[list[str]], python: str, _source_paths: list[str]) -> list[dict]:
        rows = []
        for cmd in commands:
            argv = [arg.replace("{python}", python) for arg in cmd]
            proc = subprocess.run(argv, cwd=repo, capture_output=True, text=True, timeout=10)
            rows.append({"command": cmd, "exit": proc.returncode, "output": proc.stdout + proc.stderr})
        return rows

    def test_preflight_and_same_implementation_step(self) -> None:
        config = context_matrix.load_config(self.config_path)
        self.assertEqual(
            context_matrix.ARMS,
            ("spine-pkg", "spine-openspec", "openspec", "speckit"),
        )
        prompts = []

        def fake_model(_config, repo, _out, label, instruction, thread):
            self.assertEqual(label, "implement")
            self.assertIsNone(thread)
            prompts.append(instruction)
            (repo / "value.txt").write_text("good\n")
            return None, {"usage": {"input": 100, "output": 20}, "api_list_price_equivalent_usd": 0.001}

        with patch.object(context_matrix, "check_commands", self.offline_checks), \
             patch.object(context_matrix, "model_step", fake_model):
            result = context_matrix.prepare(config)
            self.assertEqual(len(prompts), 0)
            with self.assertRaisesRegex(ValueError, "requires --approved"):
                context_matrix.run(config, approved=False)
            context_matrix.run(config, approved=True)
        self.assertEqual(len(prompts), 4)
        for arm, instruction in zip(context_matrix.ARMS, prompts, strict=True):
            self.assertIn(f"Context from {arm}.", instruction)
            self.assertEqual(instruction.split("Framework context:")[0],
                             prompts[0].split("Framework context:")[0])
        results = json.loads((result / "RESULTS.json").read_text())
        self.assertTrue(results["comparable"])
        self.assertTrue(all(row["accepted"] for row in results["arms"]))
        self.assertTrue(all(row["model_calls"] == 1 for row in results["arms"]))
        with self.assertRaisesRegex(ValueError, "already started"):
            context_matrix.run(config, approved=True)

    def test_changed_context_is_rejected_before_any_model_call(self) -> None:
        config = context_matrix.load_config(self.config_path)
        with patch.object(context_matrix, "check_commands", self.offline_checks):
            context_matrix.prepare(config)
        Path(config["contexts"]["speckit"]).write_text("tampered")
        with patch.object(context_matrix, "model_step") as model:
            with self.assertRaisesRegex(ValueError, "context changed"):
                context_matrix.run(config, approved=True)
            model.assert_not_called()

    def test_invalid_known_fix_stops_and_preserves_preflight_reason(self) -> None:
        config = context_matrix.load_config(self.config_path)
        Path(config["known_fix_patch"]).write_text("")
        with patch.object(context_matrix, "check_commands", self.offline_checks), \
             patch.object(context_matrix, "model_step") as model:
            with self.assertRaisesRegex(ValueError, "Known fix patch could not apply"):
                context_matrix.prepare(config)
            model.assert_not_called()
        failure = json.loads((Path(config["results_dir"]) / "PREFLIGHT_FAILED.json").read_text())
        self.assertEqual(failure["model_execution"], "not started")
        self.assertIn("Known fix", failure["error"])

    def test_virtualenv_interpreter_symlink_is_preserved(self) -> None:
        interpreter = self.root / "venv" / "bin" / "python"
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(sys.executable)
        raw = json.loads(self.config_path.read_text())
        raw["application_python"] = str(interpreter)
        self.config_path.write_text(json.dumps(raw))
        self.assertEqual(context_matrix.load_config(self.config_path)["application_python"], str(interpreter))

    def test_model_shell_imports_the_disposable_source(self) -> None:
        config = context_matrix.load_config(self.config_path)
        clone = self.root / "disposable"
        env = codex_environment(config, clone)
        self.assertEqual(env["PYTHONPATH"].split(os.pathsep), [str(clone), str(clone / "src")])

    def test_test_sandbox_failure_stops_remaining_arms_without_scoring(self) -> None:
        config = context_matrix.load_config(self.config_path)
        calls = []

        def fake_model(_config, repo, _out, label, _instruction, _thread):
            calls.append(label)
            (repo / "value.txt").write_text("good\n")
            return None, {"usage": {"input": 10, "output": 2}}

        def checks(repo, commands, python, paths):
            if calls and commands == config["checks"]:
                return [{"exit": 71, "output": "sandbox-exec: sandbox_apply: Operation not permitted"}]
            return self.offline_checks(repo, commands, python, paths)

        with patch.object(context_matrix, "check_commands", checks), \
             patch.object(context_matrix, "model_step", fake_model):
            result = context_matrix.prepare(config)
            context_matrix.run(config, approved=True)
        self.assertEqual(calls, ["implement"])
        payload = json.loads((result / "RESULTS.json").read_text())
        self.assertFalse(payload["comparable"])
        self.assertEqual(payload["arms"][0]["status"], "invalid_protocol")
        self.assertEqual(payload["arms"][1]["status"], "not_started")

    def test_added_regression_assertion_keeps_frozen_baseline_tests(self) -> None:
        config = context_matrix.load_config(self.config_path)

        def fake_model(_config, repo, _out, _label, _instruction, _thread):
            (repo / "value.txt").write_text("good\n")
            with (repo / "test_acceptance.py").open("a") as stream:
                stream.write("assert Path('value.txt').read_text().startswith('good')\n")
            return None, {"usage": {"input": 10, "output": 2}}

        with patch.object(context_matrix, "check_commands", self.offline_checks), \
             patch.object(context_matrix, "model_step", fake_model):
            result = context_matrix.prepare(config)
            context_matrix.run(config, approved=True)
        rows = json.loads((result / "RESULTS.json").read_text())["arms"]
        self.assertTrue(all(row["accepted"] for row in rows))
        self.assertTrue(all(row["protected_checks_unchanged"] for row in rows))
        self.assertTrue(all(row["code_patch_changed"] for row in rows))
        for arm in context_matrix.ARMS:
            original = (self.root / "work" / "runs" / arm / "evaluation" / "test_acceptance.py").read_text()
            self.assertNotIn("startswith", original)


if __name__ == "__main__":
    unittest.main()
