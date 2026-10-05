import json
from pathlib import Path
import tempfile
import unittest

from report_usage import summarize_usage


class UsageReportTests(unittest.TestCase):
    def test_exported_records_deduplicate_and_exclude_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{'type': 'turn_context', 'payload': {'model': 'gpt-6-sol'}},
                    {'type': 'token_usage_record', 'payload': {'response_id': 'r1',
                     'usage': {'input_tokens': 100, 'cached_input_tokens': 60, 'output_tokens': 5}}}]
            for name in ('gpt-6-sol/speckit/ticket-p1/session-rollout-one.jsonl',
                         'gpt-6-sol/spine/pass1/codex-calls/id/rollout-two.jsonl',
                         'diagnostics/rollout-three.jsonl'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('\n'.join(map(json.dumps, rows)))
            result = summarize_usage(root)
            usage = result['models']['gpt-6-sol']
            self.assertEqual(result['session_files'], 2)
            self.assertEqual(usage['tokens'], 105)
            self.assertEqual(usage['requests'], 1)
            self.assertEqual(usage['uncached_input'], 40)
            self.assertAlmostEqual(usage['cost_usd'], .000142)

    def test_missing_exports_do_not_invent_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(summarize_usage(Path(tmp))['models'], {})


if __name__ == '__main__':
    unittest.main()
