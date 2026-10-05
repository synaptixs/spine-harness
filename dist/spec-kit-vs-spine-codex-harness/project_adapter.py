"""Disposable application clones and change evidence for token-only benchmarks."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile


def git(root, *args, env=None):
    return subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(root),*args],
                          env=dict(env or os.environ,GIT_OPTIONAL_LOCKS='0',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull),
                          capture_output=True,check=True).stdout


def source_fingerprint(root):
    root=Path(root).resolve()
    paths=git(root,'ls-files','-z','--cached','--others','--exclude-standard').split(b'\0')
    h=hashlib.sha256()
    for raw in sorted(set(p for p in paths if p)):
        path=root/os.fsdecode(raw);h.update(raw+b'\0')
        if path.is_symlink():h.update(b'link:'+os.readlink(path).encode())
        elif path.is_file():h.update(path.read_bytes())
        else:h.update(b'<absent>')
    common=Path(os.fsdecode(git(root,'rev-parse','--git-common-dir')).strip())
    if not common.is_absolute():common=root/common
    metadata={}
    for name in ('config','index','HEAD','packed-refs'):
        path=common/name
        metadata[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return {'head':git(root,'rev-parse','HEAD').decode().strip(),
            'status':git(root,'status','--porcelain=v1','-z','--untracked-files=all').decode(),
            'working_files_sha256':h.hexdigest(),'git_metadata_sha256':metadata}


def disposable_clone(source, dest, commit):
    source=Path(source).resolve();dest=Path(dest).resolve()
    if dest.exists():raise ValueError(f'Refusing existing clone destination: {dest}')
    if dest.is_relative_to(source):raise ValueError('Disposable clone must be outside the original repository')
    before=source_fingerprint(source)
    sha=git(source,'rev-parse','--verify',commit+'^{commit}').decode().strip()
    dest.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['git','-c','core.hooksPath=/dev/null','clone','--no-hardlinks','--no-checkout',str(source),str(dest)],
                   capture_output=True,check=True,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
    git(dest,'checkout','--detach',sha)
    git(dest,'remote','remove','origin')
    git(dest,'config','core.hooksPath','/dev/null')
    if source_fingerprint(source)!=before:raise RuntimeError('Original repository changed during clone preparation')
    return sha


def capture_changes(root, baseline, destination):
    """Capture staged/unstaged, new, deleted, renamed, and binary changes without editing the index."""
    root=Path(root).resolve();destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='benchmark-index-') as temp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(temp)/'index'),GIT_OPTIONAL_LOCKS='0')
        git(root,'read-tree','HEAD',env=env)
        git(root,'add','--all','--','.',':(exclude).benchmark-tmp',env=env)
        patch=git(root,'diff','--cached','--binary','--no-ext-diff','--no-textconv',baseline,'--',env=env)
        names=git(root,'diff','--cached','--name-status','-z',baseline,'--',env=env)
    (destination/'changes.patch').write_bytes(patch)
    # Fence longer than any sequence in the patch, preventing accidental fence termination.
    import re
    body=patch.decode('utf-8',errors='replace')
    fence='`'*max(3,1+max((len(x) for x in re.findall(r'`+',body)),default=0))
    (destination/'CHANGES.md').write_text('# Proposed changes\n\nThese changes exist only in the disposable benchmark copy.\n\n'
        + (f'{fence}diff\n{body}\n{fence}\n' if patch else 'No changes captured.\n'))
    return {'baseline':baseline,'patch_sha256':hashlib.sha256(patch).hexdigest(),
            'changed':bool(patch),'name_status_z':names.decode(errors='replace'),
            'patch':'changes.patch','markdown':'CHANGES.md'}


def clean_test_env(root, paths):
    # Do not give project tests provider, Jira, GitHub, or cloud credentials.
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL','TMPDIR','SYSTEMROOT')}
    env.update(PYTHONPATH=os.pathsep.join(str(Path(root)/p) for p in paths),
               PYTHONDONTWRITEBYTECODE='1',GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
    return env


def sandboxed_command(command, root):
    """Fail closed: model-generated tests may not write outside their disposable copy."""
    root=Path(root).resolve()
    if sys.platform!='darwin' or not shutil.which('sandbox-exec'):
        raise RuntimeError('Project execution currently requires macOS sandbox-exec for isolated test/check commands')
    temporary=root/'.benchmark-tmp';temporary.mkdir(exist_ok=True)
    policy='(version 1)(allow default)(deny file-write*)(deny network*)' + \
        '(allow file-write* (subpath '+json.dumps(str(root))+') (literal "/dev/null"))'
    return ['sandbox-exec','-p',policy,*command], temporary


@dataclass
class ProjectAdapter:
    config: dict

    @classmethod
    def read(cls,path):
        data=json.loads(Path(path).read_text())
        for field in ('repository_url','source_repo','baseline_commit','target_dir','python','source_paths','checks'):
            if field not in data:raise ValueError(f'Project config missing {field}')
        if not isinstance(data['checks'],list) or any(not isinstance(c,list) or not c or any(not isinstance(x,str) for x in c) for c in data['checks']):
            raise ValueError('checks must be argv arrays, never shell strings')
        for rel in data['source_paths']:
            if Path(rel).is_absolute() or '..' in Path(rel).parts:raise ValueError('source_paths must be repository-relative')
        return cls(data)

    def verify_target(self):
        target=Path(self.config['target_dir']).resolve();source=Path(self.config['source_repo']).resolve()
        if target==source or target.is_relative_to(source):raise ValueError('Target must be outside original repository')
        if git(target,'rev-parse','HEAD').decode().strip()!=self.config['baseline_commit']:
            raise ValueError('Target baseline changed')
        if not (target/'.git').is_dir() or (target/'.git/objects/info/alternates').exists():
            raise ValueError('Target must be an independent clone, not a linked worktree/shared object store')
        if git(target,'remote').strip():raise ValueError('Benchmark clone must have no remotes')

    def run_tests(self,root,files):
        if not files:return False,'No model-generated tests were supplied'
        command=[self.config['python'],'-m','pytest','-q','-p','no:cacheprovider',*files]
        try:
            command,temporary=sandboxed_command(command,root)
            env=clean_test_env(root,self.config['source_paths']);env['TMPDIR']=str(temporary)
            p=subprocess.run(command,cwd=root,env=env,
                             capture_output=True,text=True,timeout=300)
            return p.returncode==0,(p.stdout+p.stderr)[-20000:]
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:return False,str(exc)

    def checks(self,root):
        result=[]
        for command in self.config['checks']:
            argv=[part.replace('{python}',self.config['python']) for part in command]
            try:
                argv,temporary=sandboxed_command(argv,root)
                env=clean_test_env(root,self.config['source_paths']);env['TMPDIR']=str(temporary)
                p=subprocess.run(argv,cwd=root,env=env,
                                 capture_output=True,text=True,timeout=300)
                result.append({'command':command,'exit':p.returncode,'output':(p.stdout+p.stderr)[-20000:]})
            except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
                result.append({'command':command,'exit':None,'error':str(exc)})
        return result

    def verify_execution_sandbox(self):
        root=Path(self.config['target_dir'])
        argv,temp=sandboxed_command([self.config['python'],'-c','import pytest; print("sandbox ready")'],root)
        result=subprocess.run(argv,cwd=root,env=clean_test_env(root,self.config['source_paths']),capture_output=True,text=True)
        if result.returncode:raise RuntimeError('Project runtime/sandbox unavailable: '+result.stderr[-1000:])

    def install(self, cb):
        """Use Spine's real PKG/codegen while replacing repository-specific plumbing."""
        from types import SimpleNamespace
        adapter=self
        cb.load_local_env=lambda *args,**kwargs:None
        cb.run_pytest=self.run_tests
        cb.grade=lambda *args:(True,{'fit_not_evaluated_tokens_only':True})
        cb.make_worktree=lambda name,repo_root: self._new_clone(name,repo_root)
        # Preserve generated copies until the operator retires them; no source worktree registrations.
        cb.drop_worktree=lambda *args,**kwargs:None
        class Checks:
            async def capture_baseline(self,*,path):
                return SimpleNamespace(findings={},skipped=(),describe=lambda:'project commands; token-only correctness unverified')
            async def run(self,*,path,baseline=None):
                rows=adapter.checks(path)
                return SimpleNamespace(passed=all(r.get('exit')==0 for r in rows),
                                       output=json.dumps(rows) if rows else 'No project checks configured; correctness unverified')
        cb.SubprocessPreflightRunner=Checks

    def _new_clone(self,name,repo_root):
        target=Path(tempfile.mkdtemp(prefix=f'jira-bench-{name}-'))/'repo'
        disposable_clone(repo_root,target,self.config['baseline_commit'])
        return target
