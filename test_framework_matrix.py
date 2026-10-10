import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from framework_matrix import (
    doctor,
    evaluate_swebench,
    export_swebench,
    fetch_swebench,
    grounding_preflight,
    implementation_patch,
    load,
    openspec_active_changes,
    package,
    prepare,
    protected_hashes,
    report,
    run,
    run_codex_framework,
    run_spine_worker,
    sha,
    task_from_file,
    task_material,
    timing_evidence,
    write_html,
)
from framework_spine_openspec import draft_stage, feature_stages
from project_adapter import capture_changes


class MatrixTests(unittest.TestCase):
    def test_spine_matrix_pin_is_explicit_and_immutable(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp))
            original = load(config)
            self.assertEqual(original["spine_commit"], "a8952c1a14fc31601fb5721b77b61e36003287e3")
            payload = json.loads(config.read_text())
            payload.update(spine_commit="a" * 40, spine_ref="develop+fix")
            config.write_text(json.dumps(payload))
            self.assertEqual(load(config)["spine_commit"], "a" * 40)
            payload["spine_commit"] = "a" * 7
            config.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "full 40-character Git commit"):
                load(config)

    def test_patch_capture_skips_ignored_scratch_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / ".gitignore").write_text(".benchmark-tmp/\n")
            (repo / "app.py").write_text("value = 0\n")
            subprocess.run(["git", "-C", str(repo), "add", "--all"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-qm",
                    "baseline",
                ],
                check=True,
            )
            baseline = subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            (repo / "app.py").write_text("value = 1\n")
            scratch = repo / ".benchmark-tmp"
            scratch.mkdir()
            (scratch / "output.log").write_text("test output\n")
            result = capture_changes(repo, baseline, Path(temp) / "evidence")
            patch_text = (Path(temp) / "evidence/changes.patch").read_text()
            self.assertTrue(result["changed"])
            self.assertIn("value = 1", patch_text)
            self.assertNotIn("output.log", patch_text)

    def test_spine_draft_stage_keeps_cache_and_wall_time(self):
        stage = draft_stage(
            [
                {
                    "usage": {"input": 100, "cached": 80, "output": 5, "requests": 1},
                    "wall_s": 2.5,
                    "cost_usd": 0.01,
                    "usage_complete": True,
                }
            ]
        )
        self.assertEqual(stage["known_tokens"], 105)
        self.assertEqual(stage["usage"]["cached"], 80)
        self.assertEqual(stage["wall_s"], 2.5)

    def test_spine_feature_stages_include_unstaged_intake_response(self):
        summary = {
            "prompt_tokens": 250,
            "completion_tokens": 25,
            "calls": 2,
            "cost_usd": 0.04,
            "stages": {
                "implement": {
                    "calls": 1,
                    "prompt_tokens": 150,
                    "completion_tokens": 15,
                    "cost_usd": 0.025,
                }
            },
        }
        stages = feature_stages(summary)
        self.assertEqual([stage["stage"] for stage in stages], ["feature_intake_spec", "implement"])
        self.assertEqual(stages[0]["known_tokens"], 110)
        self.assertEqual(sum(stage["known_tokens"] for stage in stages), 275)
        self.assertAlmostEqual(sum(stage["api_list_price_equivalent_usd"] for stage in stages), 0.04)

    def test_shared_task_context_is_present_in_every_framework_prompt(self):
        task = {
            "title": "Rank incidents",
            "description": "Add a ranked search method.",
            "context": {"users": "Incident operators", "outcome": "Ranked filtered results"},
        }
        material = task_material(task)
        self.assertIn("## Users\nIncident operators", material)
        self.assertIn("## Outcome\nRanked filtered results", material)
        self.assertIn("existing test_*.py files", material)
        self.assertIn("Add new tests in new files", material)

    def test_grounding_preflight_stops_before_model_when_owner_is_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "owner.py").write_text("class OwnerExtractor: pass\n")
            config = {
                "tools_dir": str(root / "tools"),
                "required_grounding": {"symbols": ["OwnerExtractor"], "files": ["owner.py"]},
            }
            task = {"title": "Fix calls", "description": "Repair the graph."}
            with patch("framework_matrix.subprocess.run") as model_process:
                result = grounding_preflight(config, repo, task)
            self.assertFalse(result["passed"])
            self.assertEqual(result["missing_from_task"], ["OwnerExtractor"])
            model_process.assert_not_called()

    def test_grounding_preflight_checks_pinned_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "owner.py").write_text("class OwnerExtractor: pass\n")
            config = {
                "tools_dir": str(root / "tools"),
                "required_grounding": {"symbols": ["OwnerExtractor"], "files": ["owner.py"]},
            }
            task = {"title": "OwnerExtractor calls", "description": "Repair the graph."}
            payload = {
                "context_chars": 99,
                "symbols_present": {"OwnerExtractor": True},
                "files_present": {"owner.py": True},
                "symbol_headers": ["### OwnerExtractor"],
            }
            with patch(
                "framework_matrix.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
            ) as process:
                result = grounding_preflight(config, repo, task)
            self.assertTrue(result["passed"])
            self.assertTrue(process.call_args.kwargs["input"].find("OwnerExtractor") >= 0)
            self.assertEqual(process.call_args.args[0][0], str(root / "tools/.venv/bin/python"))

    def test_grounding_preflight_accepts_qualified_python_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "owner.py").write_text("def api_search(): pass\n")
            tools = root / "tools"
            interpreter = tools / ".venv/bin/python"
            interpreter.parent.mkdir(parents=True)
            interpreter.symlink_to(sys.executable)
            package = tools / "src/orchestrator/sdlc"
            package.mkdir(parents=True)
            (package.parent / "__init__.py").write_text("")
            (package / "__init__.py").write_text("")
            (package / "grounding.py").write_text(
                "class PKGCodegenGrounder:\n"
                "    @classmethod\n"
                "    def from_repo(cls, root, use_cache=False): return cls()\n"
                "    def context_for_spec(self, spec):\n"
                "        return '### Function `py:wizard.app.api_search`  @ owner.py:1\\n'\n"
            )
            config = {
                "tools_dir": str(tools),
                "required_grounding": {
                    "symbols": ["wizard.app.api_search"],
                    "files": ["owner.py"],
                },
            }
            task = {
                "title": "Repair wizard.app.api_search",
                "description": "Restore the existing owner.",
            }
            result = grounding_preflight(config, repo, task)
            self.assertTrue(result["passed"])
            self.assertTrue(result["symbols_present"]["wizard.app.api_search"])

    def test_protected_hashes_include_public_script_and_requirement_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "checks").mkdir()
            (repo / ".spine").mkdir()
            (repo / "checks/ask_ui.js").write_text("console.log('check');\n")
            (repo / ".spine/required-behavior.yaml").write_text("requirements: []\n")
            hashes = protected_hashes(repo, [])
            self.assertIn("checks/ask_ui.js", hashes)
            self.assertIn(".spine/required-behavior.yaml", hashes)

    def test_sleep_gap_invalidates_time_comparison(self):
        start = "2026-10-10T12:43:33+00:00"
        end = "2026-10-10T13:18:05+00:00"
        evidence = timing_evidence(start, end, 811.4)
        self.assertFalse(evidence["timing_comparable"])
        self.assertGreater(evidence["unaccounted_wall_s"], 1200)
        self.assertTrue(timing_evidence(start, "2026-10-10T12:57:05+00:00", 811.4)["timing_comparable"])

    def test_clock_gap_stops_before_next_arm_and_preserves_partial_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, _, _ = self.fixture(root)
            payload = json.loads(config.read_text())
            second = dict(payload["frameworks"][0], name="second-framework")
            payload["frameworks"].append(second)
            config.write_text(json.dumps(payload))
            c = load(config)
            prepare(c)
            with (
                patch("framework_matrix.sandboxed_command", side_effect=lambda cmd, repo: (cmd, repo)),
                patch(
                    "framework_matrix.timing_evidence",
                    return_value={"utc_elapsed_s": 100, "unaccounted_wall_s": 90, "timing_comparable": False},
                ),
            ):
                result = run(c, approved=True)
            rows = json.loads((result / "RESULTS.json").read_text())["runs"]
            self.assertEqual(len(rows), 1)
            self.assertEqual((result / "EXIT_CODE").read_text().strip(), "2")
            self.assertTrue((result / "RUN_INVALID.json").is_file())
            report_text = (result / "COMPARISON_REPORT.md").read_text()
            self.assertIn("1/2 arms have final evidence", report_text)
            self.assertIn("no framework ranking or score is valid", report_text)
            with self.assertRaisesRegex(ValueError, "incomplete|invalid|Interrupted"):
                package(result)

    def test_scope_resolutions_are_shared_and_validated_before_run(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp))
            data = json.loads(config.read_text())
            data["question_answers"] = {"Is the built-in case included?": "No; it is a separate issue."}
            data["unresolved_question_policy"] = {"mode": "defer", "owner": "issue-owner"}
            config.write_text(json.dumps(data))
            c = load(config)
            from framework_matrix import task_material

            text = task_material(
                {
                    "title": "Fix extension",
                    "description": "Resolve imported receiver",
                    "question_answers": c["question_answers"],
                    "unresolved_question_policy": c["unresolved_question_policy"],
                }
            )
            self.assertIn("No; it is a separate issue.", text)
            self.assertIn("Defer any remaining scope questions to @issue-owner", text)
            data["unresolved_question_policy"] = {"mode": "defer"}
            config.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "named owner"):
                load(config)

    def test_doctor_model_smoke_requires_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp))
            with self.assertRaisesRegex(ValueError, "requires --approved"):
                doctor(load(config), smoke_model=True)

    def test_spine_adapter_uses_pinned_interpreter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            python = root / "tools/.venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("")
            out = root / "out"
            out.mkdir()
            commands = []

            def worker(command, **kwargs):
                commands.append((command, kwargs))
                (out / "STAGES.json").write_text(json.dumps([{"stage": "draft", "known_tokens": 10}]))
                return SimpleNamespace(returncode=0)

            with patch("framework_matrix.subprocess.run", side_effect=worker):
                stages = run_spine_worker(
                    {"tools_dir": str(root / "tools"), "login_home": str(root / "login"), "timeout_seconds": 30},
                    {"id": "TASK-1"},
                    root / "common",
                    root / "repo",
                    out,
                    "baseline",
                )
            self.assertEqual(commands[0][0][0], str(python))
            self.assertEqual(stages[0]["known_tokens"], 10)

    def test_spine_pkg_uses_distinct_native_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            python = root / "tools/.venv/bin/python"
            python.parent.mkdir(parents=True)
            python.write_text("")
            out = root / "out"
            out.mkdir()
            commands = []

            def worker(command, **_kwargs):
                commands.append(command)
                (out / "STAGES.json").write_text(json.dumps([{"stage": "feature_intake_spec", "known_tokens": 10}]))
                return SimpleNamespace(returncode=0)

            with patch("framework_matrix.subprocess.run", side_effect=worker):
                run_spine_worker(
                    {"tools_dir": str(root / "tools"), "login_home": str(root / "login"), "timeout_seconds": 30},
                    {"id": "TASK-1"},
                    root / "common",
                    root / "repo",
                    out,
                    "baseline",
                    "spine-pkg",
                )
            self.assertTrue(commands[0][1].endswith("framework_spine_pkg.py"))

    def test_reference_task_preserves_structured_spec_for_native_spine(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "task.json"
            spec = {
                "title": "Feature",
                "summary": "Add a feature",
                "technical_notes": "Reuse API",
                "acceptance_criteria": ["Returns value"],
            }
            file.write_text(
                json.dumps({"id": "TASK-1", "title": "Feature", "description": "Add a feature", "spec": spec})
            )
            self.assertEqual(task_from_file(file)["spec"], spec)
            file.write_text(
                json.dumps({"id": "TASK-1", "title": "Feature", "description": "Add a feature", "spec": []})
            )
            with self.assertRaisesRegex(ValueError, "spec must be an object"):
                task_from_file(file)

    def test_html_report_renders_tables_links_and_escapes_task_text(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "report.html"
            write_html(
                target,
                "Pilot report",
                "# Pilot report\n\n| Arm | Result |\n|---|---|\n| OpenSpec | [patch](runs/pass1/openspec/changes.patch) |\n\n## Detail\n\n<script>alert(1)</script>",
                [],
            )
            page = target.read_text()
            self.assertIn("<table>", page)
            self.assertIn('href="runs/pass1/openspec/changes.patch"', page)
            self.assertIn("<h2>Detail</h2>", page)
            self.assertNotIn("<script>", page)

    def test_openspec_selects_new_change_when_baseline_has_existing_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            changes = repo / "openspec/changes"
            (changes / "existing-change").mkdir(parents=True)
            (changes / "archive").mkdir()
            out = root / "out"
            out.mkdir()
            prompts = []
            commands = []

            def command(argv, **_kwargs):
                commands.append(argv)
                return SimpleNamespace(returncode=0, stdout="valid", stderr="")

            def model(_config, _repo, _out, label, prompt, _thread):
                prompts.append((label, prompt))
                if label == "propose":
                    (changes / "new-change").mkdir()
                    (changes / "new-change/proposal.md").write_text("# Proposal\n")
                return "thread", {"stage": label, "last_message_tail": "done"}

            self.assertEqual(openspec_active_changes(repo), {"existing-change"})
            with (
                patch("framework_matrix.codex_environment", return_value={}),
                patch("framework_matrix.subprocess.run", side_effect=command),
                patch("framework_matrix.model_step", side_effect=model),
                patch("framework_matrix.run_sessions", return_value=[]),
            ):
                run_codex_framework(
                    {"login_home": str(root / "login")},
                    {"id": "TASK-1", "title": "Feature", "description": "Build it"},
                    "openspec",
                    repo,
                    out,
                )
            self.assertIn(["openspec", "validate", "new-change", "--strict", "--no-interactive"], commands)
            self.assertIn("$openspec-apply-change new-change", prompts[1][1])
            self.assertEqual(json.loads((out / "OPENSPEC_CHANGE.json").read_text())["change"], "new-change")

    def test_official_patch_excludes_framework_scaffolding(self):
        raw = "diff --git a/.specify/config.md b/.specify/config.md\nnew file mode 100644\n+plan\n"
        raw += "diff --git a/tests/test_feature.py b/tests/test_feature.py\n--- a/tests/test_feature.py\n+++ b/tests/test_feature.py\n+assert True\n"
        raw += "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n+answer = 1\n"
        self.assertNotIn(".specify/config.md", implementation_patch(raw))
        self.assertNotIn("tests/test_feature.py", implementation_patch(raw))
        self.assertIn("diff --git a/app.py", implementation_patch(raw))

    def fixture(self, root, kind="jira"):
        source = root / "source"
        source.mkdir()
        (source / "app.py").write_text("answer = 0\n")
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "add",
                "app.py",
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "-qm",
                "baseline",
            ],
            check=True,
        )
        baseline = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        task = root / "task.json"
        if kind == "jira":
            task.write_text(
                json.dumps({"key": "TEAM-1", "fields": {"summary": "Change answer", "description": "Make answer one"}})
            )
        else:
            task.write_text(
                json.dumps(
                    {
                        "instance_id": "owner__repo-1",
                        "repo": "owner/repo",
                        "base_commit": baseline,
                        "problem_statement": "Make answer one",
                        "test_patch": "SECRET_HIDDEN_TEST",
                    }
                )
            )
        adapter = root / "adapter.py"
        adapter.write_text("""import json, os, pathlib, sys
repo, output = map(pathlib.Path, sys.argv[1:])
(repo / 'app.py').write_text('answer = 1\\n')
(output / 'USAGE.json').write_text(json.dumps({'model':'gpt-6-sol','reasoning_effort':'high',
 'stages':[{'name':'implement','complete':True,'responses':[{'response_id':'r1',
 'usage':{'input_tokens':100,'cached_input_tokens':20,'output_tokens':10}}]}]}))
""")
        config = root / "matrix.json"
        config.write_text(
            json.dumps(
                {
                    "name": "matrix-one",
                    "source_repo": str(source),
                    "baseline": baseline,
                    "task_file": str(task),
                    "model": "gpt-6-sol",
                    "reasoning_effort": "high",
                    "login_home": str(root / "login"),
                    "work_dir": str(root / "work"),
                    "results_dir": str(root / "results"),
                    "frameworks": [{"name": "my-framework", "argv": ["python3", str(adapter), "{repo}", "{output}"]}],
                    "checks": [],
                    "acceptance_checks": [],
                }
            )
        )
        return config, source, task

    def test_public_swe_task_does_not_expose_hidden_test_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, task = self.fixture(Path(temp), "swebench")
            normalized = task_from_file(task)
            self.assertNotIn("SECRET_HIDDEN_TEST", json.dumps(normalized))
            self.assertEqual(normalized["id"], "owner__repo-1")
            self.assertEqual(normalized["kind"], "swebench")
            self.assertEqual(load(config)["baseline"], normalized["baseline"])

    def test_external_adapter_end_to_end_and_official_prediction_export(self):
        with tempfile.TemporaryDirectory() as temp:
            config, source, _ = self.fixture(Path(temp), "swebench")
            c = load(config)
            prepared = prepare(c)
            self.assertEqual((prepared / "TASK.json").exists(), True)
            self.assertEqual((source / "app.py").read_text(), "answer = 0\n")
            result = run(c, approved=True)
            row = json.loads((result / "RESULTS.json").read_text())["runs"][0]
            self.assertEqual(row["status"], "completed_workflow")
            self.assertEqual(row["usage"]["known_tokens"], 110)
            self.assertTrue(row["usage"]["complete"])
            self.assertTrue(row["changes"]["changed"])
            self.assertEqual((source / "app.py").read_text(), "answer = 0\n")
            self.assertIn("my-framework", report(result).read_text())
            self.assertIn("Functional check results", (result / "COMPARISON_REPORT.md").read_text())
            self.assertEqual(
                json.loads((result / "USAGE_EVIDENCE.json").read_text())[0]["entries"][0]["response_id"], "r1"
            )
            self.assertIn("<!doctype html>", (result / "COMPARISON_REPORT.html").read_text())
            paths = export_swebench(result)
            self.assertEqual(len(paths), 1)
            prediction = json.loads(paths[0].read_text())
            self.assertEqual(set(prediction), {"instance_id", "model_name_or_path", "model_patch"})
            self.assertIn("+answer = 1", prediction["model_patch"])
            archive = package(result)
            with zipfile.ZipFile(archive) as contents:
                self.assertIsNone(contents.testzip())
                self.assertTrue(any(p.endswith("EVIDENCE_VERIFICATION.json") for p in contents.namelist()))
                self.assertTrue(any(p.endswith("USAGE_EVIDENCE.json") for p in contents.namelist()))
                self.assertTrue(any(p.endswith("my-framework-pass1.jsonl") for p in contents.namelist()))

    def test_prepare_and_run_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp))
            c = load(config)
            prepare(c)
            with self.assertRaisesRegex(ValueError, "Existing work/results"):
                prepare(c)
            run(c, approved=True)
            with self.assertRaisesRegex(ValueError, "already started"):
                run(c, approved=True)

    def test_failed_baseline_preparation_saves_diagnostics(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp))
            c = load(config)
            with patch(
                "framework_matrix.check_commands",
                return_value=[{"command": ["pytest"], "exit": 71, "output": "sandbox unavailable"}],
            ):
                with self.assertRaisesRegex(ValueError, "no model run started"):
                    prepare(c)
            failure = json.loads((Path(c["work_dir"]) / "PREPARATION_FAILED.json").read_text())
            self.assertEqual(failure["checks"][0]["exit"], 71)
            self.assertFalse(Path(c["results_dir"]).exists())

    def test_external_acceptance_file_is_frozen_before_model_work(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, _, _ = self.fixture(root)
            acceptance = root / "test_acceptance.py"
            acceptance.write_text(
                "from pathlib import Path\ndef test_feature(): assert Path('app.py').read_text() == 'answer = 1\\n'\n"
            )
            data = json.loads(config.read_text())
            data["acceptance_checks"] = [["{python}", "-m", "pytest", "{config_dir}/test_acceptance.py"]]
            config.write_text(json.dumps(data))
            c = load(config)
            with patch("framework_matrix.sandboxed_command", side_effect=lambda cmd, repo: (cmd, repo)):
                prepared = prepare(c)
            saved = json.loads((prepared / "PREPARED.json").read_text())
            self.assertEqual(saved["external_acceptance_inputs"][str(acceptance.resolve())], sha(acceptance))
            self.assertEqual(len(list((prepared / "frozen-acceptance").iterdir())), 1)
            acceptance.write_text("def test_feature(): assert False\n")
            with self.assertRaisesRegex(ValueError, "External acceptance input changed"):
                run(c, approved=True)

    def test_acceptance_that_passes_on_baseline_stops_before_model(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, _, _ = self.fixture(root)
            acceptance = root / "test_acceptance.py"
            acceptance.write_text("def test_feature(): assert True\n")
            data = json.loads(config.read_text())
            data["acceptance_checks"] = [["{python}", "-m", "pytest", str(acceptance)]]
            config.write_text(json.dumps(data))
            c = load(config)
            with patch("framework_matrix.sandboxed_command", side_effect=lambda cmd, repo: (cmd, repo)):
                with self.assertRaisesRegex(ValueError, "Baseline acceptance did not fail"):
                    prepare(c)
            failure = json.loads((Path(c["work_dir"]) / "PREPARATION_FAILED.json").read_text())
            self.assertEqual(failure["stage"], "baseline independent acceptance")
            self.assertFalse(Path(c["results_dir"]).exists())

    def test_known_fix_commit_passes_independent_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config, source, _ = self.fixture(root)
            acceptance = root / "test_acceptance.py"
            acceptance.write_text(
                "from pathlib import Path\ndef test_feature(): assert Path('app.py').read_text() == 'answer = 1\\n'\n"
            )
            (source / "app.py").write_text("answer = 1\n")
            subprocess.run(["git", "-C", str(source), "add", "app.py"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(source),
                    "-c",
                    "user.name=Test",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-qm",
                    "known fix",
                ],
                check=True,
            )
            fixed = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
            data = json.loads(config.read_text())
            data["acceptance_checks"] = [["{python}", "-m", "pytest", str(acceptance)]]
            data["known_fix_commit"] = fixed
            config.write_text(json.dumps(data))
            with patch("framework_matrix.sandboxed_command", side_effect=lambda cmd, repo: (cmd, repo)):
                prepared = prepare(load(config))
            evidence = json.loads((prepared / "PREPARED.json").read_text())
            self.assertEqual(evidence["baseline_acceptance_checks"][0]["exit"], 1)
            self.assertEqual(evidence["known_fix_evidence"]["commit"], fixed)
            self.assertEqual(evidence["known_fix_evidence"]["acceptance_checks"][0]["exit"], 0)

    def test_official_verdict_comes_from_instance_report(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp), "swebench")
            c = load(config)
            prepare(c)
            result = run(c, approved=True)
            prediction = export_swebench(result)[0]

            def evaluator(command, *, cwd, stdout, stderr):
                run_id = command[command.index("--run_id") + 1]
                instance = command[command.index("--instance_ids") + 1]
                path = cwd / "logs" / "evaluation" / run_id / "model" / instance / "report.json"
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps({instance: {"resolved": True}}))
                return SimpleNamespace(returncode=0)

            with patch("framework_matrix.subprocess.run", side_effect=evaluator):
                evaluate_swebench(result, prediction, "SWE-bench/SWE-bench_Verified")
            verdict = json.loads((result / "SWE_EVALUATIONS.json").read_text())[0]
            self.assertIs(verdict["resolved"], True)
            self.assertIn("Official SWE-bench evaluation", (result / "COMPARISON_REPORT.md").read_text())

    def test_clone_failure_is_preserved_as_incomplete_measurement(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp))
            c = load(config)
            prepare(c)
            with patch("framework_matrix.disposable_clone", side_effect=RuntimeError("clone unavailable")):
                result = run(c, approved=True)
            row = json.loads((result / "RESULTS.json").read_text())["runs"][0]
            self.assertEqual(row["status"], "workflow_failed")
            self.assertFalse(row["usage"]["complete"])
            self.assertFalse(row["changes"]["changed"])
            self.assertTrue((result / "JOB_FAILED").is_file())

    def test_interrupted_run_is_not_marked_successful(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, _ = self.fixture(Path(temp))
            c = load(config)
            prepare(c)
            with patch("framework_matrix.run_external", side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    run(c, approved=True)
            result = Path(c["results_dir"])
            self.assertEqual((result / "EXIT_CODE").read_text().strip(), "130")
            self.assertFalse(json.loads((result / "INTERRUPTED.json").read_text())["result_is_comparable"])
            self.assertFalse((result / "RESULTS.json").exists())
            with self.assertRaisesRegex(ValueError, "Interrupted or incomplete"):
                package(result)

    def test_fetch_one_official_row_then_hide_gold_patches(self):
        with tempfile.TemporaryDirectory() as temp:
            config, _, task = self.fixture(Path(temp), "swebench")
            task.unlink()
            c = load(config)
            row = {
                "instance_id": "owner__repo-1",
                "repo": "owner/repo",
                "base_commit": c["baseline"],
                "problem_statement": "Make answer one",
                "patch": "HIDDEN_GOLD",
                "test_patch": "HIDDEN_TEST",
            }
            fake = SimpleNamespace(load_dataset=lambda *_args, **_kwargs: iter([row]))
            with patch.dict(sys.modules, {"datasets": fake}):
                fetched = fetch_swebench(c, "SWE-bench/SWE-bench_Verified", "owner__repo-1")
            self.assertEqual(fetched, task.resolve())
            self.assertIn("HIDDEN_GOLD", task.read_text())
            self.assertNotIn("HIDDEN_GOLD", json.dumps(task_from_file(task)))
            self.assertNotIn("HIDDEN_TEST", json.dumps(task_from_file(task)))


if __name__ == "__main__":
    unittest.main()
