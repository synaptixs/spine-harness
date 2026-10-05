import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from benchmark import load_config, config_digest
from deliverables import finalize, read_ledgers, unknown_calls, archive_evidence


class PortableTests(unittest.TestCase):
    def config(self, root):
        c = {'name': 'pilot', 'source_repo': str(root / 'source'), 'repository_url': 'https://example.test/repo',
             'jira_url': 'https://example.atlassian.net', 'issues': ['TEAM-12'], 'snapshots': ['inputs/TEAM-12.json'],
             'checks': [['{python}', '-m', 'pytest', '-q', 'tests']]}
        p = root / 'benchmark.json'; p.write_text(json.dumps(c)); return p, c

    def fixture(self, root, incomplete=False):
        exp = {'models': ['gpt-6-sol'], 'arms': ['speckit', 'spine'], 'tickets': ['TEAM-12'], 'passes': 1, 'scenario_fingerprint': 'frozen'}
        (root / 'EXPERIMENT.json').write_text(json.dumps(exp)); (root / 'FINISHED').write_text('closed')
        events = [{'type': 'turn_context', 'payload': {'model': 'gpt-6-sol'}},
                  {'type': 'token_usage_record', 'payload': {'response_id': 'response-1', 'usage': {'input_tokens': 100, 'cached_input_tokens': 40, 'output_tokens': 20}}}]
        for arm, parent in [('speckit', root / 'gpt-6-sol/speckit/team-12-p1'), ('spine', root / 'gpt-6-sol/spine/pass1/TEAM-12')]:
            parent.mkdir(parents=True)
            summary = {'ticket': 'TEAM-12', 'pass': 1, 'model': 'gpt-6-sol', 'arm': arm, 'scenario_fingerprint': 'frozen',
                       'usage_complete': not incomplete, 'aborted': incomplete, 'prompt_tokens': 100, 'completion_tokens': 20,
                       'tests_pass': True, 'project_checks': [{'exit': 0}], 'cost_usd': .01}
            (parent / 'summary.json').write_text(json.dumps(summary)); (parent / 'changes.patch').write_text('diff --git a/a.py b/a.py\n')
        p = root / 'gpt-6-sol/speckit/team-12-p1/session-rollout-main.jsonl'
        p.write_text('\n'.join(map(json.dumps, events)))
        p = root / 'gpt-6-sol/spine/pass1/codex-calls/call'; p.mkdir(parents=True)
        events[1]['payload']['response_id'] = 'response-2'
        (p / 'rollout-main.jsonl').write_text('\n'.join(map(json.dumps, events)))
        (p / 'request.json').write_text('{}'); (p / 'usage.json').write_text(json.dumps({'usage_complete': not incomplete}))

    def test_config_paths_are_relocatable_and_login_not_inside_results(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); p, c = self.config(root); loaded = load_config(p)
            self.assertEqual(loaded['snapshots'], [str((root / 'inputs/TEAM-12.json').resolve())])
            self.assertEqual(loaded['results_dir'], str((root / 'results/pilot').resolve()))
            c['login_home'] = 'results/pilot/login'; p.write_text(json.dumps(c))
            with self.assertRaises(ValueError): load_config(p)

    def test_windows_json_bom_and_path_rejection(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); p, c = self.config(root)
            p.write_text(json.dumps(c), encoding='utf-8-sig')
            self.assertEqual(load_config(p)['issues'], ['TEAM-12'])
            c['source_repo'] = 'C:/code/app'; p.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError, 'WSL paths'): load_config(p)
            c['source_repo'] = str(root/'source'); c['application_python'] = 'C:/venv/python.exe'
            p.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError, 'interpreter'): load_config(p)

    def test_venv_interpreter_symlink_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); p, c = self.config(root)
            base = root / 'base-python'; base.write_text(''); venv = root / 'venv/bin'; venv.mkdir(parents=True)
            (venv / 'python').symlink_to(base); c['application_python'] = str(venv / 'python'); p.write_text(json.dumps(c))
            self.assertEqual(load_config(p)['application_python'], str(venv / 'python'))

    def test_closed_reports_archive_and_portable_reconciliation(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); self.fixture(root)
            (root / 'auth.json').write_text('{"access_token":"secret"}'); (root / 'benchmark.env').write_text('PRIVATE=secret')
            out = finalize(root)
            usage = json.loads((out / 'USAGE.json').read_text())
            self.assertEqual(usage['models']['gpt-6-sol']['tokens'], 240)
            self.assertTrue(usage['complete'])
            with zipfile.ZipFile(out / 'results-and-artifacts.zip') as z:
                self.assertIsNone(z.testzip()); names = z.namelist()
                self.assertFalse(any(n.endswith(('auth.json', 'benchmark.env', '.jsonl', 'request.json')) for n in names))
                self.assertTrue(any(n.endswith('response-ledger.json') for n in names))
                target = root / 'unpacked'; z.extractall(target)
            # Copying just the portable evidence still permits response-ledger verification.
            copied = target / root.name
            records, origins = read_ledgers(copied)
            self.assertEqual(len(records), 2); self.assertEqual(len(origins), 2)

    def test_failed_usage_is_unknown_and_no_zero_cost_claim(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); self.fixture(root, incomplete=True)
            out = finalize(root); usage = json.loads((out / 'USAGE.json').read_text())
            self.assertFalse(usage['complete']); self.assertEqual(len(usage['unknown_calls']), 1)
            self.assertIn('known subtotals', (out / 'FINAL_REPORT.md').read_text())
            with zipfile.ZipFile(out / 'results-and-artifacts.zip') as z: z.extractall(root / 'export')
            self.assertEqual(len(unknown_calls(root / 'export' / root.name)), 1)

    def test_active_run_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); self.fixture(root); (root / 'RUNNING.json').write_text('{}')
            with self.assertRaises(ValueError): finalize(root)

    def test_secret_and_symlink_packaging(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); out = root / 'deliverables'; out.mkdir()
            p = root / 'unexpected.txt'; p.write_text('-----BEGIN ' + 'PRIVATE KEY-----')
            with self.assertRaises(ValueError): archive_evidence(root, out)
            p.unlink(); (root / 'link.txt').symlink_to('/etc/passwd')
            archive = archive_evidence(root, out)
            with zipfile.ZipFile(archive) as z: self.assertFalse(any(n.endswith('link.txt') for n in z.namelist()))

    def test_duplicate_conflicting_response_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t); self.fixture(root)
            p = root / 'gpt-6-sol/speckit/team-12-p1/session-rollout-other.jsonl'
            p.write_text(json.dumps({'type': 'turn_context', 'payload': {'model': 'gpt-6-sol'}})+'\n'+json.dumps({'type': 'token_usage_record', 'payload': {'response_id': 'response-1', 'usage': {'input_tokens': 99}}}))
            with self.assertRaises(ValueError): read_ledgers(root)

if __name__ == '__main__': unittest.main()
