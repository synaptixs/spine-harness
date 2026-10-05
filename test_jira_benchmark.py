import asyncio
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from jira_import import fetch_mcp, normalize, save_import, unwrap
from project_adapter import (
    ProjectAdapter,
    capture_changes,
    disposable_clone,
    source_fingerprint,
)
from scenario_catalog import load_catalog


def run_git(path,*args):
    return subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True).stdout


class JiraTests(unittest.TestCase):
    def issue(self):
        return {'key':'ONTM-123','fields':{'summary':'Handle empty input','description':{'type':'doc','content':[
            {'type':'paragraph','content':[{'type':'text','text':'First '},{'type':'text','text':'requirement.'}]},
            {'type':'paragraph','content':[{'type':'text','text':'Second requirement.'}]}]},'customfield_ac':'Return an empty list.'}}

    def test_rich_text_and_missing_criteria_are_not_invented(self):
        row=normalize(self.issue())
        self.assertEqual(row['spec']['summary'],'First requirement.\nSecond requirement.')
        self.assertEqual(row['spec']['acceptance_criteria'],[])
        self.assertEqual(normalize(self.issue(),'customfield_ac')['spec']['acceptance_criteria'],['Return an empty list.'])
        self.assertEqual(row['kind'],'change')

    def test_unwrap_and_frozen_catalog(self):
        wrapped={'structuredContent':{'result':json.dumps(self.issue())}}
        self.assertEqual(unwrap(wrapped),self.issue())
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'import'
            file=save_import([wrapped],dest,'https://example.atlassian.net/jira')
            rows,meta=load_catalog(file)
            self.assertEqual(meta['evaluation_mode'],'tokens-only')
            self.assertEqual(rows[0]['held_out_tests'],{})
            self.assertFalse(json.loads((dest/'REVIEW.json').read_text())['reviewed'])
            with self.assertRaises(ValueError):save_import([wrapped],dest,'https://example.atlassian.net')

    def test_fail_closed_for_empty_or_incomplete_issues(self):
        for issue in ({'key':'ONTM','summary':'x','description':'y'},{'key':'ONTM-1','summary':'x'}, {'isError':True}):
            with self.assertRaises(ValueError):normalize(unwrap(issue))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):save_import([],Path(d)/'x','https://example.atlassian.net')
            self.assertFalse((Path(d)/'x').exists())

    def test_mcp_uses_only_read_tool_and_disables_history(self):
        @dataclass
        class Config:
            name:str='jira';enabled:bool=True;allow:tuple=();write_enabled:bool=True
        calls=[]
        issue=self.issue()
        class Client:
            def __init__(self,config):
                self.config=config
                assert config.allow==('jira_get_issue',) and config.write_enabled is False
            async def call_tool(self,name,args):
                calls.append((name,args))
                return types.SimpleNamespace(is_error=False,structured={'result':json.dumps(issue)},text='')
        modules={'orchestrator.mcp.config':types.SimpleNamespace(load_mcp_configs=lambda _: [Config()]),
                 'orchestrator.mcp.client':types.SimpleNamespace(SessionMCPClient=Client)}
        with patch.dict(sys.modules,modules):
            result=asyncio.run(fetch_mcp('ignored','jira',['ONTM-123']))
        self.assertEqual(result,[issue]);self.assertEqual(calls[0][0],'jira_get_issue')
        self.assertIs(calls[0][1]['update_history'],False);self.assertEqual(calls[0][1]['comment_limit'],0)


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        run_git(self.source,'init')
        for name,body in [('edit.txt','old\n'),('delete.txt','delete\n'),('rename.txt','rename\n')]:
            (self.source/name).write_text(body)
        (self.source/'binary.bin').write_bytes(b'\0old')
        run_git(self.source,'add','.')
        run_git(self.source,'-c','user.name=Test','-c','user.email=test@example.invalid','-c','core.hooksPath=/dev/null','commit','-m','baseline')
        self.sha=run_git(self.source,'rev-parse','HEAD').decode().strip()

    def test_clone_and_patch_preserve_dirty_source_and_index(self):
        (self.source/'edit.txt').write_text('user change\n')
        before=source_fingerprint(self.source)
        clone=self.root/'clone';disposable_clone(self.source,clone,self.sha)
        self.assertEqual((clone/'edit.txt').read_text(),'old\n')
        self.assertEqual(run_git(clone,'remote'),b'')
        (clone/'edit.txt').write_text('proposed\n');run_git(clone,'add','edit.txt')
        (clone/'delete.txt').unlink();(clone/'rename.txt').rename(clone/'renamed.txt')
        (clone/'new file.txt').write_text('new\n');(clone/'binary.bin').write_bytes(b'\0new')
        idx=(clone/'.git/index').read_bytes()
        evidence=capture_changes(clone,self.sha,self.root/'results')
        patch_text=(self.root/'results/changes.patch').read_text()
        for expected in ('proposed','deleted file mode','new file.txt','GIT binary patch','renamed.txt'):
            self.assertIn(expected,patch_text)
        self.assertTrue(evidence['changed']);self.assertEqual((clone/'.git/index').read_bytes(),idx)
        self.assertEqual(source_fingerprint(self.source),before)

    def test_adapter_refuses_original_repository(self):
        config={'source_repo':str(self.source),'target_dir':str(self.source),'baseline_commit':self.sha}
        with self.assertRaises(ValueError):ProjectAdapter(config).verify_target()

    def test_project_execution_is_disabled_before_model_calls(self):
        cfg=self.root/'project.json';cfg.write_text(json.dumps({'repository_url':'https://example.invalid/repo',
            'source_repo':str(self.source),'target_dir':str(self.root/'target'),'baseline_commit':self.sha,
            'python':sys.executable,'source_paths':['.'],'checks':[]}))
        env=dict(os.environ,PROJECT_CONFIG=str(cfg),BENCHMARK_EXECUTE='0',SPINE_REPO=str(self.source),
                 UV_CACHE_DIR=str(self.root/'cache'),UV_PYTHON_INSTALL_DIR=str(self.root/'python'))
        script=Path(__file__).with_name('run_comparison.py')
        result=subprocess.run([sys.executable,str(script),'--models','gpt-6-sol'],env=env,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('Project execution disabled',result.stderr)

    def test_report_includes_patch_and_missing_attempts(self):
        from report_project import report
        root=self.root/'results';path=root/'gpt-6-sol/speckit/ontm-123-p1';path.mkdir(parents=True)
        exp={'evaluation_mode':'tokens-only','tickets':['ONTM-123'],'passes':1,'models':['gpt-6-sol'],
             'arms':['speckit','spine'],'scenario_fingerprint':'abc','project':{'repository_url':'https://example.invalid/repo','baseline_commit':self.sha}}
        (root/'EXPERIMENT.json').write_text(json.dumps(exp))
        (path/'summary.json').write_text(json.dumps({'ticket':'ONTM-123','pass':1,'model':'gpt-6-sol','scenario_fingerprint':'abc','total':{'tokens':100,'cost_usd':.001}}))
        (path/'CHANGES.md').write_text('```diff\n+example change\n```')
        report(root);text=(root/'RESULTS.md').read_text()
        self.assertIn('+example change',text);self.assertIn('Missing Spine + PKG',text)
        self.assertIn('unverified',text);self.assertIn('no exported Codex response ledger',text)


if __name__=='__main__':unittest.main()
