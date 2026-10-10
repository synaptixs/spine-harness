"""Offline integration: the actual production loop, PKG and codegen use scripted model outputs."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from project_adapter import ProjectAdapter, git, source_fingerprint
from spine_feature import FeatureBoundary, protected_files, run_project_ticket


class OpenSpecQuestionIntegrationTests(unittest.TestCase):
    def test_recorded_answer_and_named_deferral_clear_native_question_gate(self):
        from orchestrator.intake.intents import Intent
        from orchestrator.intake.openspec_writer import render_change, write_change
        from orchestrator.intake.requirements import check_intent, load_change
        from orchestrator.intake.specs import FeatureSpec

        from framework_spine_openspec import record_preapproved_questions

        question = "Is the built-in receiver case included?"
        for config, expected in (
            ({"question_answers": {question: "No; it is a separate issue."},
              "unresolved_question_policy": {"mode": "stop"}}, "answered"),
            ({"question_answers": {},
              "unresolved_question_policy": {"mode": "defer", "owner": "issue-owner"}}, "deferred"),
        ):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                intent = Intent(id="intent-fix", title="Fix imported receiver", description="Resolve the extension",
                                problem="Calls target the wrong function", users=["Graph readers"],
                                outcome="The call targets the local extension", non_goals=["Keep library members"],
                                open_questions=[question])
                spec = FeatureSpec(intent_id=intent.id, title=intent.title, summary=intent.description)
                write_change(root, intent, render_change(spec, intent))
                change = load_change("fix", root=root)
                self.assertIn(question, check_intent(change.intent).unresolved)
                resolved = record_preapproved_questions(change, config, root, root)
                report = check_intent(resolved.intent)
                self.assertNotIn(question, report.unresolved)
                evidence = json.loads((root / "OPENSPEC_RESOLUTIONS.json").read_text())
                self.assertEqual(evidence["recorded"][0]["status"], expected)


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='feature-integration-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root/'target'; self.repo.mkdir()
        git(self.repo, 'init')
        files = {
            'pyproject.toml': '[project]\nname="fixture-app"\nversion="0.0.1"\n',
            'app.py': 'def helper():\n    return 0\n\ndef default():\n    return []\n',
            'tests/test_existing.py': 'def test_regression():\n    assert 1 + 1 == 2\n',
            'checks/default_check.py': 'from app import default\nassert default() == [42], "default output must contain 42"\n',
            '.spine/required-behavior.yaml': 'requirements:\n  - id: default-output\n    description: default returns 42\n    entry_point: default\n    command: [python3, checks/default_check.py]\n    required: true\n',
        }
        for name, text in files.items():
            p = self.repo/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        git(self.repo, 'add', '.')
        git(self.repo, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'baseline')
        self.project = ProjectAdapter({'target_dir': str(self.repo), 'source_repo': str(self.repo),
            'baseline_commit': git(self.repo, 'rev-parse', 'HEAD').decode().strip(), 'python': sys.executable,
            'source_paths': ['.'], 'require_behavior': True, 'max_refine': 1,
            'checks': [['{python}', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', 'tests/test_existing.py']]})

    def scripted(self, *, repair=True, tamper=False, review_break=False):
        from orchestrator.core.llm.client import CompletionResult, ToolCall
        owner = self

        class Client:
            def __init__(self):
                self.n = 0
                self.messages = []

            async def complete(self, messages, **kwargs):
                self.n += 1
                self.messages.append(str(messages))
                name = kwargs['tool_choice']
                if name != 'submit_files':
                    # Match the native semantic review tool schema, without mocking the judge.
                    args = {'criteria': [{'criterion': 'Default returns 42', 'status': 'met', 'evidence': 'default calls helper'}], 'summary': 'met'}
                    if review_break:
                        (owner.workrepo/'app.py').write_text('def helper():\n    return 42\n\ndef default():\n    return []\n')
                elif self.n == 1:
                    args = {'files': [{'path': 'app.py', 'edits': [{'find': 'return 0', 'replace': 'return 42'}]}], 'summary': 'helper'}
                elif self.n == 2:
                    args = {'files': [{'path': 'tests/test_generated.py', 'content': 'from app import helper\ndef test_helper():\n    assert helper() == 42\n'}], 'summary': 'tests'}
                else:
                    if tamper:
                        args = {'files': [{'path': 'checks/default_check.py', 'edits': [{'find': 'assert default() == [42]', 'replace': 'assert True'}]}], 'summary': 'tamper'}
                    else:
                        args = {'files': [{'path': 'app.py', 'edits': [{'find': 'return []', 'replace': 'return [helper()]' if repair else 'return [0]'}]}], 'summary': 'default wiring'}
                return CompletionResult(text=json.dumps(args), model=kwargs['model'], prompt_tokens=100,
                    completion_tokens=20, cost_usd=.001, latency_ms=1, tool_calls=(ToolCall(str(self.n), name, args),))
        return Client()

    def run_case(self, **kwargs):
        client = self.scripted(**kwargs)
        before = source_fingerprint(self.repo)
        # Narrow transport substitution: remove only OS sandbox wrapping when unit
        # tests run inside an outer sandbox that cannot nest sandbox-exec. Separate
        # confinement test exercises the real wrapper.
        real_sandbox = os.environ.get("TEST_REAL_SANDBOX") == "1"
        def local_command(argv, root):
            temp = Path(root)/'.benchmark-tmp'; temp.mkdir(exist_ok=True)
            self.workrepo = Path(root)
            if real_sandbox:
                from project_adapter import sandboxed_command
                return sandboxed_command(argv, root)
            return argv, temp
        with patch('spine_feature.sandboxed_command', local_command):
            result = asyncio.run(run_project_ticket(self.project, SimpleNamespace(key='TEAM-1', spec={
                'title': 'Connect default', 'summary': 'Default must return the helper result',
                'acceptance_criteria': ['Default returns 42'], 'technical_notes': ''}),
                'gpt-6-sol', self.root/'results/pass1/TEAM-1', self.root/'calls', client=client))
        self.assertEqual(source_fingerprint(self.repo), before)
        return result, client

    def test_native_failure_refines_and_passes(self):
        result, client = self.run_case()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['status'], 'verified_selected_behaviors')
        self.assertFalse(result['required_behavior'][0]['passed'])
        self.assertTrue(result['required_behavior'][-1]['passed'])
        self.assertEqual(result['refines'], 1)
        self.assertIn('default output must contain 42', client.messages[2])
        self.assertEqual(result['stages']['required_behavior']['calls'], 0)
        self.assertGreater(result['stages']['required_behavior']['deterministic_seconds'], 0)
        self.assertEqual(sum(s['calls'] for s in result['stages'].values()), client.n)
        self.assertIn('semantic_review', result['stages'])

    def test_failure_stops_at_native_refinement_limit(self):
        result, _ = self.run_case(repair=False)
        self.assertFalse(result['passed'])
        self.assertEqual(result['refines'], 1)
        self.assertFalse(result['required_behavior'][-1]['passed'])

    def test_modified_public_check_cannot_pass(self):
        result, _ = self.run_case(tamper=True)
        self.assertFalse(result['passed'])

    def test_final_gate_detects_post_gate_revision(self):
        result, _ = self.run_case(review_break=True)
        self.assertFalse(result['passed'])
        self.assertTrue(any(x['passed'] for x in result['required_behavior']))
        self.assertFalse(result['required_behavior'][-1]['passed'])

    def test_missing_manifest_refused_before_models(self):
        (self.repo/'.spine/required-behavior.yaml').unlink()
        with self.assertRaisesRegex(ValueError, 'required'):
            protected_files(self.repo, self.project.config)

    def test_public_checks_prepared_in_clone_only(self):
        from project_benchmark import prepare
        before = source_fingerprint(self.repo)
        extra = self.root/'extra.py'; extra.write_text('assert True\n')
        profile = self.root/'profile.json'
        profile.write_text(json.dumps({'repository_url': 'https://example.invalid/repo',
            'jira_url': 'https://example.invalid', 'jira_project': 'TEAM',
            'baseline_commit': before['head'], 'checks': self.project.config['checks'],
            'source_paths': ['.'], 'behavior_files': {'checks/new.py': str(extra)}}))
        # Only the existence of the pinned tools script is needed for preparation.
        tools = self.root/'tools'; (tools/'scripts').mkdir(parents=True)
        (tools/'scripts/codegen_benchmark.py').write_text('')
        prepare(profile, self.repo, tools, self.root/'prepared', self.root/'prepared-results', sys.executable)
        config = json.loads((self.root/'prepared-results/PROJECT.json').read_text())
        self.assertNotEqual(config['baseline_commit'], before['head'])
        self.assertTrue((self.root/'prepared/target/checks/new.py').exists())
        self.assertFalse((self.repo/'checks/new.py').exists())
        self.assertEqual(source_fingerprint(self.repo), before)
        self.assertIn('checks/new.py', config['behavior_protected_files'])

    def test_call_budget_stops_and_retains_evidence(self):
        self.project.config['max_model_calls'] = 2
        result, client = self.run_case()
        self.assertEqual(result['status'], 'budget_exhausted')
        self.assertEqual(client.n, 2)
        self.assertTrue((self.root/'results/pass1/TEAM-1/changes.patch').exists())

    @unittest.skipUnless(os.environ.get('TEST_REAL_SANDBOX') == '1', 'opt-in real OS confinement check')
    def test_application_cannot_write_outside_or_receive_secrets(self):
        boundary = FeatureBoundary(self.project, self.repo, self.root/'evidence')
        rc, output = asyncio.run(boundary.capture([sys.executable, '-c', 'print(42)'], cwd=self.repo))
        self.assertEqual(rc, 0, output)
        outside = self.root/'outside.txt'
        with patch.dict(os.environ, {'JIRA_API_TOKEN': 'never-expose'}):
            rc, out = asyncio.run(boundary.capture([sys.executable, '-c',
                'import os; from pathlib import Path; assert "JIRA_API_TOKEN" not in os.environ; '
                f'Path({str(outside)!r}).write_text("bad")'], cwd=self.repo))
        self.assertNotEqual(rc, 0)
        self.assertFalse(outside.exists())


if __name__ == '__main__':
    unittest.main()
