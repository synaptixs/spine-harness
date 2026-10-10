import json
import tempfile
import unittest
from pathlib import Path

from matrix_study import build, exact_sign_p


class StudyTests(unittest.TestCase):
    def test_exact_sign_test_uses_independent_directions(self):
        self.assertEqual(exact_sign_p([2.0] * 6), 0.03125)
        self.assertEqual(exact_sign_p([2.0] * 5), 0.0625)
        self.assertEqual(exact_sign_p([1.0, 1.0]), None)

    def task(
        self,
        root: Path,
        task_id: str,
        tokens: int,
        version: str = "1.0",
        repository: str = "https://github.com/synaptixs/ontomesh",
    ) -> Path:
        root.mkdir()
        (root / "FINISHED").write_text("closed\n")
        (root / "COMPARISON_REPORT.md").write_text("# Per-task report\n")
        (root / "EVIDENCE_VERIFICATION.json").write_text(
            json.dumps(
                {
                    "normalized_task_unchanged": True,
                    "original_source_unchanged": True,
                    "functional_comparison_valid": True,
                    "wall_time_comparison_valid": True,
                }
            )
        )
        data = {
            "experiment": {
                "task": {"id": task_id, "kind": "jira"},
                "repository_url": repository,
                "model": "gpt-6-sol",
                "reasoning_effort": "high",
                "frameworks": ["my-framework"],
                "framework_versions": {"my-framework": version},
                "passes": 1,
            },
            "runs": [
                {
                    "pass": 1,
                    "framework": "my-framework",
                    "status": "completed_workflow",
                    "usage": {"complete": True, "known_tokens": tokens, "api_list_price_equivalent_usd": 0.01},
                    "workflow_wall_s": 12.5,
                    "total_wall_s": 15.0,
                    "selected_checks_passed": True,
                    "regression_checks": [{"exit": 0}],
                    "acceptance_checks": [{"exit": 0}],
                    "protected_inputs_unchanged": True,
                }
            ],
        }
        (root / "RESULTS.json").write_text(json.dumps(data))
        return root

    def test_two_task_aggregate_preserves_denominators(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.task(root / "a", "TEAM-1", 100)
            second = self.task(root / "b", "TEAM-2", 200)
            report = build([first, second], root / "study")
            result = json.loads((report.parent / "MATRIX_STUDY_RESULTS.json").read_text())
            self.assertEqual(result["aggregates"][0]["total_recorded_tokens_complete_rows"], 300)
            self.assertEqual(result["aggregates"][0]["acceptance_evaluated"], 2)
            self.assertEqual(result["aggregates"][0]["official_evaluated"], 0)
            self.assertEqual(result["aggregates"][0]["selected_checks_passed"], 2)
            self.assertEqual(result["aggregates"][0]["median_workflow_wall_s"], 12.5)
            self.assertAlmostEqual(result["aggregates"][0]["total_api_list_price_equivalent_usd_complete_rows"], 0.02)
            self.assertIn("TEAM-2", report.read_text())
            self.assertIn("API-equivalent cost", report.read_text())
            self.assertNotIn("Official SWE-bench resolution", report.read_text())
            self.assertIn("<!doctype html>", (report.parent / "MATRIX_STUDY_REPORT.html").read_text())

    def test_duplicate_task_or_mixed_version_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.task(root / "a", "TEAM-1", 100)
            duplicate = self.task(root / "b", "TEAM-1", 200)
            with self.assertRaisesRegex(ValueError, "duplicate task"):
                build([first, duplicate], root / "study")
            data = json.loads((duplicate / "RESULTS.json").read_text())
            data["experiment"]["task"]["id"] = "TEAM-2"
            data["experiment"]["framework_versions"]["my-framework"] = "2.0"
            (duplicate / "RESULTS.json").write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "versions"):
                build([first, duplicate], root / "study")

    def test_same_issue_id_in_different_repositories_is_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.task(root / "a", "ISSUE-1", 100)
            second = self.task(root / "b", "ISSUE-1", 200, repository="https://github.com/synaptixs/spine")
            report = build([first, second], root / "study")
            result = json.loads((report.parent / "MATRIX_STUDY_RESULTS.json").read_text())
            self.assertEqual(len(result["repositories"]), 2)
            self.assertEqual(len(result["repository_aggregates"]), 2)

    def test_invalid_clock_evidence_cannot_enter_study(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.task(root / "a", "TEAM-1", 100)
            second = self.task(root / "b", "TEAM-2", 200)
            evidence = json.loads((second / "EVIDENCE_VERIFICATION.json").read_text())
            evidence["wall_time_comparison_valid"] = False
            (second / "EVIDENCE_VERIFICATION.json").write_text(json.dumps(evidence))
            with self.assertRaisesRegex(ValueError, "Invalid or incomplete benchmark protocol"):
                build([first, second], root / "study")


if __name__ == "__main__":
    unittest.main()
