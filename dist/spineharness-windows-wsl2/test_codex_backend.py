import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import asyncio

import harness_config as C
C.use_tree(C.SPINE_CODE_DIR)
from codex_llm import complete, output_contract, restore_optional, strict_schema
from codex_usage import records, total, cost
from codex_protocol import needs_checklist_approval
from orchestrator.sdlc.codegen import _SUBMIT_TOOL
from orchestrator.core.llm.client import LLMError
from orchestrator.core.llm.client import Message
import jsonschema


class BackendTests(unittest.TestCase):
    def test_checklist_confirmation_wording(self):
        self.assertTrue(needs_checklist_approval('Checklist unchecked. Proceed? (yes/no)'))
        self.assertTrue(needs_checklist_approval('Implementation is paused at the checklist gate. Do you want me to proceed anyway? Reply **yes** to continue or **no** to wait.'))
        self.assertFalse(needs_checklist_approval('Implementation complete; all tests pass.'))

    def test_deduplicate_and_ignore_inherited_totals(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            sessions = home / "sessions"
            sessions.mkdir()
            record = {"type": "token_usage_record", "payload": {
                "response_id": "a", "usage": {"input_tokens": 100, "cached_input_tokens": 60,
                "cache_write_input_tokens": 10, "output_tokens": 5}}}
            meta = {"type": "session_meta", "payload": {"cwd": "/tmp/one"}}
            junk = {"payload": {"type": "token_count", "info": {
                "last_token_usage": {"input_tokens": 999999}}}}
            for name in ["a", "b"]:
                (sessions / f"{name}.jsonl").write_text("\n".join(map(json.dumps, [meta, record, record, junk])))
            self.assertEqual(total(records(home, Path('/tmp/one'))),
                             {"input": 100, "cached": 60, "cache_write": 10,
                              "output": 5, "reasoning": 0, "requests": 1})
            self.assertEqual(total(records(home, Path('/tmp/other')))['requests'], 0)

    def test_optional_file_fields_round_trip(self):
        schema, name = output_contract(tools=[_SUBMIT_TOOL], tool_choice='submit_files')
        value = {"files": [{"path": "new.py", "content": "x = 1\n", "edits": None}], "summary": None}
        jsonschema.validate(value, strict_schema(schema))
        restored = restore_optional(value, schema)
        jsonschema.validate(restored, schema)
        self.assertEqual(restored, {"files": [{"path": "new.py", "content": "x = 1\n"}]})
        self.assertEqual(name, 'submit_files')

    def test_existing_file_edits_round_trip(self):
        schema = _SUBMIT_TOOL.parameters
        value = {"files": [{"path": "old.py", "content": None,
                 "edits": [{"find": "old", "replace": "new"}]}], "summary": "Fix"}
        jsonschema.validate(value, strict_schema(schema))
        restored = restore_optional(value, schema)
        self.assertNotIn('content', restored['files'][0])
        jsonschema.validate(restored, schema)

    def test_unsupported_tool_contract_fails(self):
        with self.assertRaises(LLMError):
            output_contract(tools=[_SUBMIT_TOOL], tool_choice=None)

    def test_cost_separates_cache_and_fails_unknown_model(self):
        usage = {"input": 100, "cached": 60, "cache_write": 10, "output": 5}
        self.assertAlmostEqual(cost('gpt-5.6-sol', usage), .000294)
        with self.assertRaises(KeyError):
            cost('unknown', usage)

    def test_subscription_environment_excludes_api_credentials(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test', 'CODEX_API_KEY': 'test'}):
            with patch.object(C, 'CODEX_AUTH', 'app'):
                self.assertNotIn('OPENAI_API_KEY', C.codex_env())
                self.assertNotIn('CODEX_API_KEY', C.codex_env())


class CompletionTests(unittest.IsolatedAsyncioTestCase):
    async def call(self, *, exit_code=0, tool_action=False, with_usage=True, envelope=False, malformed=False):
        class Proc:
            returncode = exit_code
            async def communicate(self, prompt):
                events = [{'type': 'item.completed', 'item': {'type': 'agent_message',
                           'text': '{"files":[{"path":"x.py","content":"x=1","edits":null}],"summary":null}'}},
                          {'type': 'turn.completed'}]
                if envelope:
                    item = events[0]['item']
                    item['text'] = json.dumps({'text': item['text']})
                if malformed:
                    events[0]['item']['text'] = '{invalid'
                if tool_action:
                    events.append({'type': 'item.completed', 'item': {'type': 'command_execution'}})
                self.stdout.write('\n'.join(map(json.dumps, events)).encode())
                self.stdout.flush()
                return None, None
        async def create(*args, **kwargs):
            self.assertIn('--ignore-user-config', args)
            self.assertIn('read-only', args)
            self.assertIn('shell_tool', args)
            self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
            proc = Proc()
            proc.stdout = kwargs['stdout']
            return proc
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict('os.environ', {'CODEX_OUTPUT_MODE': 'envelope' if envelope else 'schema'}), \
                 patch.multiple(C, WORK_DIR=Path(tmp)/'work', RESULTS_DIR=Path(tmp)/'results',
                                CODEX_AUTH='app', STOP=Path(tmp)/'STOP'):
                with patch('codex_llm.asyncio.create_subprocess_exec', create), \
                     patch('codex_llm.records', return_value={'r': {'input_tokens':100,'output_tokens':5}} if with_usage else {}), \
                     patch('codex_llm.run_sessions', return_value=[]):
                    return await complete(None, [Message('user','Generate x')], model='gpt-5.6-sol',
                                          tools=[_SUBMIT_TOOL], tool_choice='submit_files')

    async def test_completion_maps_tool_payload_and_usage(self):
        result = await self.call()
        self.assertEqual(result.prompt_tokens, 100)
        self.assertEqual(result.tool_calls[0].arguments, {'files':[{'path':'x.py','content':'x=1'}]})

    async def test_failed_process_is_not_a_completion(self):
        with self.assertRaises(LLMError):
            await self.call(exit_code=1)

    async def test_envelope_preserves_tool_arguments(self):
        result = await self.call(envelope=True)
        self.assertEqual(result.tool_calls[0].arguments, {'files':[{'path':'x.py','content':'x=1'}]})

    async def test_tool_use_invalidates_measurement(self):
        with self.assertRaises(LLMError):
            await self.call(tool_action=True)

    async def test_missing_ledger_invalidates_measurement(self):
        with self.assertRaises(LLMError):
            await self.call(with_usage=False)

    async def test_malformed_json_is_a_protocol_error(self):
        with self.assertRaises(LLMError):
            await self.call(malformed=True)


class SummaryTests(unittest.TestCase):
    def test_successful_steps_without_code_are_not_complete(self):
        from summarize import completed
        run = {'total': {'requests': 47}, 'rows': [{'exit': 0}], 'reached_code': False}
        self.assertFalse(completed(run))
        run['reached_code'] = True
        self.assertTrue(completed(run))
        run['paused_for_checklist'] = True
        self.assertFalse(completed(run))


if __name__ == '__main__':
    unittest.main()
