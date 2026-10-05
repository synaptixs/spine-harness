import copy
from dataclasses import dataclass,field
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from scenario_catalog import CatalogError, load_catalog, configure, fingerprint, changed_python_files, split_python_files
from report_results import indexed, sign_p, completed
from model_report import model_section


@dataclass
class Ticket:
    key:str
    kind:str
    spec:dict
    must_edit:list=field(default_factory=list)
    held_out_tests:dict=field(default_factory=dict)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/'test_hidden.py').write_text('def test_result():\n    assert True\n')
        self.doc={'schema_version':1,'scenarios':[{'key':'TEAM-EDIT-1','kind':'edit','must_edit':['src/stats.py'],
                    'spec':{'title':'Add mean','summary':'Compute mean','technical_notes':'Reuse model','acceptance_criteria':['Empty is zero']},
                    'held_out_tests':['test_hidden.py']}]}
        self.path=self.root/'scenarios.json'
    def save(self):self.path.write_text(json.dumps(self.doc));return self.path
    def test_examples_are_valid(self):
        rows,meta=load_catalog(Path(__file__).parent/'examples/scenarios.json')
        self.assertEqual([r['kind'] for r in rows],['edit','create'])
        self.assertEqual(len(meta['file_sha256']),3)
    def test_test_content_changes_identity(self):
        _,a=load_catalog(self.save());(self.root/'test_hidden.py').write_text('def test_result():\n    assert False\n')
        _,b=load_catalog(self.path);self.assertNotEqual(a['catalog_sha256'],b['catalog_sha256'])
    def test_unknown_duplicate_shadow_and_missing_target(self):
        built=Ticket('BASE-ONE','create',{},held_out_tests={'test_b.py':'pass'})
        cb=SimpleNamespace(Ticket=Ticket,TICKETS=[built])
        for keys in (['UNKNOWN-ID'],['BASE-ONE','BASE-ONE']):
            with self.assertRaises(CatalogError):configure(cb,keys)
        with self.assertRaises(CatalogError):configure(cb,['TEAM-EDIT-1'],self.save(),self.root)
        self.doc['scenarios'][0]['key']='BASE-ONE'
        with self.assertRaises(CatalogError):configure(cb,['BASE-ONE'],self.save())
    def test_selected_order_and_fingerprint(self):
        built=Ticket('BASE-ONE','create',{},held_out_tests={'test_b.py':'pass'})
        cb=SimpleNamespace(Ticket=Ticket,TICKETS=[built])
        (self.root/'src').mkdir();(self.root/'src/stats.py').write_text('x=1')
        configure(cb,['TEAM-EDIT-1','BASE-ONE'],self.save(),self.root)
        self.assertEqual([t.key for t in cb.TICKETS],['TEAM-EDIT-1','BASE-ONE'])
        before=fingerprint(cb.TICKETS);cb.TICKETS[0].spec['summary']='Different'
        self.assertNotEqual(before,fingerprint(cb.TICKETS))
    def test_path_traversal_missing_and_syntax(self):
        for path in ('../escape.py','/tmp/test_bad.py','absent.py'):
            self.doc['scenarios'][0]['held_out_tests']=[path]
            with self.assertRaises(CatalogError):load_catalog(self.save())
        self.doc['scenarios'][0]['held_out_tests']=['test_hidden.py']
        (self.root/'test_hidden.py').write_text('def broken(')
        with self.assertRaises(SyntaxError):load_catalog(self.save())
    def test_duplicate_ids_and_required_criteria(self):
        self.doc['scenarios']*=2
        with self.assertRaises(CatalogError):load_catalog(self.save())
        self.doc['scenarios']=self.doc['scenarios'][:1];self.doc['scenarios'][0]['spec']['acceptance_criteria']=[]
        with self.assertRaises(CatalogError):load_catalog(self.save())


class ChangedFilesTests(unittest.TestCase):
    def test_edit_only_staged_and_untracked_are_graded(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def git(*args):subprocess.run(['git',*args],cwd=root,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            git('init');(root/'existing.py').write_text('x=1\n');(root/'test_existing.py').write_text('def test_ok(): pass\n')
            git('add','.');git('-c','user.name=Test','-c','user.email=test@example.invalid','-c','core.hooksPath=/dev/null','commit','-m','fixture')
            (root/'existing.py').write_text('x=2\n');git('add','existing.py')
            (root/'test_existing.py').write_text('def test_ok(): assert True\n')
            (root/'new file.py').write_text('y=3\n');(root/'.agents').mkdir();(root/'.agents/helper.py').write_text('x=9')
            paths=changed_python_files(root);impl,tests=split_python_files(root,paths)
            self.assertEqual({Path(p).name for p in impl},{'existing.py','new file.py'})
            self.assertEqual([Path(p).name for p in tests],['test_existing.py'])


class ReportTests(unittest.TestCase):
    def test_model_provenance_does_not_infer_missing_or_mismatched_models(self):
        groups=[('spec-kit','gpt-6-sol',[{'model':'gpt-6-astra','reasoning_effort':'high'}]),
                ('Spine + PKG','gpt-6-sol',[{}])]
        text='\n'.join(model_section({'model_reasoning_effort':'high'},groups,{'models':{}}))
        self.assertIn('**Model mismatch:**',text)
        self.assertIn('`gpt-6-astra` (1)',text)
        self.assertIn('unknown (not recorded)',text)
        self.assertIn('configured; absent from measurement rows',text)
        self.assertIn('actual response model identity is unverified',text)
        text='\n'.join(model_section({},[],{'models':{'gpt-6-sol':{'requests':1095}}}))
        self.assertIn('`gpt-6-sol` — 1,095 responses',text)

    def test_arbitrary_catalog_pairs_intake_and_defers_partial_inference(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);tickets=[f'TEAM-{i}' for i in range(5)];model='gpt-6-sol'
            def save(rel,value):
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
            save('EXPERIMENT.json',{'models':[model],'tickets':tickets,'passes':2,'arms':['speckit','spine'],
                 'scenario_fingerprint':'fixed','scenarios':[{'key':t,'kind':'edit'} for t in tickets]})
            for n in (1,2):
                intake=[]
                for t in tickets:
                    common={'ticket':t,'pass':n,'scenario_fingerprint':'fixed'}
                    save(f'{model}/speckit/{t}-p{n}/summary.json',{**common,'reached_code':True,'rows':[],
                         'total':{'cost_usd':2},'grading':{'held_out_pass':True,'repo_gate_pass':False}})
                    save(f'{model}/spine/pass{n}/{t}/summary.json',{**common,'usage_complete':True,'cost_usd':.75,
                         'held_out_pass':True,'repo_gate_pass':False})
                    intake.append({**common,'cost_usd':.25})
                save(f'{model}/intake/pass{n}.json',intake)
            cmd=[sys.executable,str(Path(__file__).with_name('report_results.py')),'--results',str(root)]
            subprocess.run(cmd,check=True,capture_output=True)
            report=(root/'summary.md').read_text()
            self.assertIn('Models used in benchmark runs',report)
            self.assertIn('Spine intake (separate)',report)
            self.assertIn('unknown (not recorded)',report)
            self.assertIn('**2.00×**',report);self.assertIn('**p = 0.0625**',report)
            p=root/f'{model}/intake/pass2.json';p.write_text(json.dumps(json.loads(p.read_text())[:-1]))
            subprocess.run(cmd,check=True,capture_output=True)
            self.assertIn('Inference deferred',(root/'summary.md').read_text())
            p=root/f'{model}/speckit/TEAM-0-p1/summary.json';v=json.loads(p.read_text());v['scenario_fingerprint']='changed';p.write_text(json.dumps(v))
            self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)

    def test_pairing_rejects_duplicate_or_wrong_ids(self):
        r={'ticket':'A','pass':1}
        self.assertEqual(indexed([r],{('A',1)}),{('A',1):r})
        with self.assertRaises(ValueError):indexed([r,r],{('A',1)})
        with self.assertRaises(ValueError):indexed([r],{('B',1)})
    def test_clusters_and_recovered_errors(self):
        self.assertEqual(sign_p([1,2,3]),.25)
        self.assertEqual(sign_p([1]*6),.03125)
        self.assertEqual(sign_p([0,0]),1)
        r={'reached_code':True,'rows':[{'step':'failed','exit':1},{'step':'resume','exit':0}]}
        self.assertFalse(completed(r))
        r['recovered_steps']={'failed':'resume'};self.assertTrue(completed(r))


if __name__=='__main__':unittest.main()
