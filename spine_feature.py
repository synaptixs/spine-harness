"""Isolated harness bindings around Spine's production feature pipeline.

The native run_feature owns generation, coverage, judgment and refinement. Only
workspace, environment and subprocess boundaries are adapted for a read-only
Jira benchmark. No harness repair loop and no hidden-test feedback.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import time
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from project_adapter import capture_changes, clean_test_env, disposable_clone, git, sandboxed_command
from spine_version import PROJECT_EXECUTION_PATH, SPINE_COMMIT, SPINE_REF


def verify_spine(tree, expected_commit=SPINE_COMMIT, expected_ref=SPINE_REF):
    tree = Path(tree)
    if git(tree, 'rev-parse', 'HEAD').decode().strip() != expected_commit:
        raise ValueError(f'Project runner requires {expected_ref} at {expected_commit}; use a fresh tools directory')
    if git(tree, 'status', '--porcelain', '--untracked-files=all', '--', 'src', 'scripts', 'pyproject.toml', 'uv.lock').strip():
        raise ValueError('Spine runtime source differs from its pinned commit')


def protected_files(root, config):
    """Protect public check inputs; never import/evaluate hidden acceptance tests."""
    from orchestrator.sdlc.required_behavior import load_manifest
    root = Path(root)
    requirements = load_manifest(root)
    if config.get('require_behavior', True) and not any(r.required for r in requirements):
        raise ValueError('A nonempty required .spine/required-behavior.yaml is required before model execution')
    names = {'.spine/required-behavior.yaml', *config.get('behavior_protected_files', [])}
    # Existing regression/check files cannot be rewritten to manufacture a pass.
    names.update(p.relative_to(root).as_posix() for p in root.rglob('test_*.py') if '.git' not in p.parts)
    for command in [r.command for r in requirements] + config['checks']:
        for arg in command[1:]:
            candidate = root / arg
            if not arg.startswith('-') and candidate.is_file():
                names.add(arg)
    hashes = {}
    for name in sorted(names):
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError(f'Protected check must be repository relative: {name}')
        p = root / rel
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):
            raise ValueError(f'Protected check symlink is unsupported: {name}')
        if not p.is_file():
            if name == '.spine/required-behavior.yaml' and not requirements:
                continue
            raise ValueError(f'Protected check is missing: {name}')
        hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


class FeatureBoundary:
    def __init__(self, project, repo, destination):
        self.project, self.repo, self.destination = project, Path(repo).resolve(), Path(destination)
        self.protected = protected_files(self.repo, project.config)
        self.behavior_results = []
        self.test_results = []
        self.project_checks = []
        self.generated_tests = []
        self.environment_blocked = False

    def guard(self):
        for rel, expected in self.protected.items():
            p = self.repo / rel
            if p.is_symlink() or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f'Frozen public check modified: {rel}')

    async def capture(self, command, *, cwd, timeout=300, **_kwargs):
        root = Path(cwd).resolve()
        if root != self.repo:
            raise RuntimeError('Application command outside the disposable repository')
        self.guard()
        argv = [str(x).replace('{python}', self.project.config['python']) for x in command]
        if argv[0] in ('python', 'python3'):
            argv[0] = self.project.config['python']
        argv, temporary = sandboxed_command(argv, root)
        env = clean_test_env(root, self.project.config['source_paths'])
        env.update(TMPDIR=str(temporary), HOME=str(temporary),
                   PATH=str(Path(self.project.config['python']).parent) + os.pathsep + env.get('PATH', ''))
        try:
            proc = await asyncio.create_subprocess_exec(*argv, cwd=root, env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except (TimeoutError, asyncio.CancelledError):
                os.killpg(proc.pid, signal.SIGKILL)
                await proc.wait()
                raise
            rc, text = proc.returncode, out.decode(errors='replace')[-20000:]
        except (OSError, TimeoutError) as exc:
            self.environment_blocked = True
            rc, text = -1, str(exc)
        if rc and ('sandbox_apply:' in text or 'bwrap:' in text):
            self.environment_blocked = True
            rc = -1
        self.guard()
        return rc, text

    async def run(self, *, path):
        """Native runner seam: generated tests plus the reviewed regression commands."""
        from orchestrator.sdlc.contracts import TestRunResult
        self.guard()
        changed = set(git(self.repo, 'diff', '--name-only', 'HEAD').decode().splitlines())
        changed.update(git(self.repo, 'ls-files', '--others', '--exclude-standard').decode().splitlines())
        tests = sorted(n for n in changed if Path(n).name.startswith('test_') and n.endswith('.py') and (self.repo/n).is_file())
        self.generated_tests = tests
        if not tests:
            return TestRunResult(passed=False, returncode=5, output='No generated tests were supplied')
        commands = [[self.project.config['python'], '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *tests], *self.project.config['checks']]
        results = []
        for cmd in commands:
            rc, out = await self.capture(cmd, cwd=path)
            results.append({'command': cmd, 'exit': rc, 'output': out})
        self.project_checks = results[1:]
        passed = bool(self.project_checks) and all(r['exit'] == 0 for r in results)
        self.test_results.append({'passed': passed, 'results': results})
        return TestRunResult(passed=passed, returncode=0 if passed else 1, output=json.dumps(results))

    def behavior_runner(self):
        from orchestrator.sdlc.required_behavior import SubprocessRequiredBehaviorRunner
        boundary = self
        native = SubprocessRequiredBehaviorRunner(capture=self.capture)

        class RecordedBehavior:
            async def run(self, *, path):
                boundary.guard()
                result = await native.run(path=path)
                boundary.guard()
                boundary.behavior_results.append(asdict(result))
                boundary.environment_blocked |= any(i.environment_blocked for i in result.items)
                return result
        return RecordedBehavior()


async def run_project_ticket(project, ticket, model, destination, calls_root, *, client=None, metadata=None,
                             source_uri=None, openspec_root=None):
    """Run the pinned production pipeline; save evidence on both success and failure."""
    from orchestrator.core.llm import LiteLLMClient, TokenLedger
    from orchestrator.sdlc import feature_runner as feature
    from orchestrator.sdlc.review import SemanticReviewAdapter

    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=False)
    # A separate repository per ticket, never the user's checkout or its git objects.
    repo = Path(project.config['target_dir']).parent / 'feature-copies' / hashlib.sha256(str(dest.resolve()).encode()).hexdigest()[:16] / ticket.key
    disposable_clone(project.config['target_dir'], repo, project.config['baseline_commit'])
    started = time.monotonic()
    boundary = FeatureBoundary(project, repo, dest)
    ledger = TokenLedger()
    prior = set(Path(calls_root).iterdir()) if Path(calls_root).exists() else set()
    logs = []
    summary = {'ticket': ticket.key, 'model': model, 'spine': SPINE_REF, 'spine_commit': SPINE_COMMIT,
               'execution_path': PROJECT_EXECUTION_PATH, 'worktree': str(repo),
               'protected_checks': boundary.protected, 'required_behavior': [], 'passed': False,
               'status': 'running', 'human_interventions': 0, **(metadata or {})}
    if source_uri:
        if not openspec_root:
            raise ValueError('OpenSpec source requires an isolated OpenSpec root')
        summary['source_uri'] = source_uri
    (dest/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')

    def emit(message):
        logs.append(message)
        print(message, flush=True)

    class Workspace:
        def __init__(self, **kwargs):
            pass

        async def create(self, *_args):
            return repo

    class Environment:
        python = project.config['python']
        declared = frozenset()

        async def ensure(self, path):
            rc, out = await boundary.capture([self.python, '-c', 'import pytest'], cwd=path)
            if rc:
                raise RuntimeError('Prepared application environment is unavailable: '+out)

        async def install(self, packages):
            return False  # Dependencies are frozen before either measured arm.

        def describe(self):
            return 'Prepared application interpreter; offline sandbox; no dependency auto-install'

    async def sandbox_exec(path, *argv):
        rc, out = await boundary.capture(argv, cwd=path)
        return rc == 0, out

    async def local_commit(path, message):
        boundary.guard()
        git(path, 'add', '-A', '--', '.')
        git(path, 'reset', '-q', 'HEAD', '--', '.benchmark-tmp')
        git(path, '-c', 'user.name=Benchmark', '-c', 'user.email=benchmark@example.invalid', 'commit', '--allow-empty', '-m', message)

    actual_client = client or LiteLLMClient()
    calls = 0
    cap = int(project.config.get('max_model_calls', 24))

    class BoundedClient:
        async def complete(self, *args, **kwargs):
            nonlocal calls
            boundary.guard()
            if calls >= cap:
                raise RuntimeError('Model call cap reached')
            if kwargs['model'] != model:
                raise RuntimeError('Unexpected model in native pipeline: '+kwargs['model'])
            calls += 1
            return await actual_client.complete(*args, **kwargs)

    # Module-scoped injection is confined to the single-ticket worker process.
    # The production loop itself, PKG, codegen and semantic judge are unchanged.
    safe_env = {k:v for k,v in os.environ.items() if k in
                ('PATH','HOME','LANG','LC_ALL','TMPDIR','SYSTEMROOT','CODEX_CALLS_DIR','CODEX_OUTPUT_MODE')}
    runtime_home = repo.parent / '.runtime-home'
    runtime_home.mkdir()
    safe_env.update(HOME=str(runtime_home), SDLC_TEST_BASELINE='0', SDLC_CODEGEN_MODEL=model,
                    GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    if source_uri:
        safe_env.update(ORCHESTRATOR_OPENSPEC_ROOT=str(Path(openspec_root).resolve()),
                        ORCHESTRATOR_INTAKE_CACHE_DIR=str(dest/'intake-cache'),
                        ORCHESTRATOR_INTAKE_MODEL=model,
                        ORCHESTRATOR_BACKLOG_PATH=str(dest/'BACKLOG.md'))
    behavior = boundary.behavior_runner()
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, safe_env, clear=True))
            for target, value in {
                'orchestrator.core.env.load_local_env': lambda *a, **k: None,
                'orchestrator.core.llm.LiteLLMClient': lambda: BoundedClient(),
                'orchestrator.sdlc.workspace.WorkspaceManager': Workspace,
                'orchestrator.sdlc.testenv.make_test_environment': lambda *a, **k: Environment(),
                'orchestrator.sdlc.testenv.make_test_runner': lambda *a, **k: boundary,
                'orchestrator.sdlc.required_behavior.SubprocessRequiredBehaviorRunner': lambda: behavior,
                'orchestrator.sdlc.review.SemanticReviewAdapter': lambda llm: SemanticReviewAdapter(llm, model=model),
                'orchestrator.sdlc.feature_runner._exec': sandbox_exec,
                'orchestrator.sdlc.feature_runner._local_commit': local_commit,
            }.items():
                stack.enter_context(patch(target, value))
            # Construct before patching its factory to prevent recursive instantiation.
            result = await feature.run_feature(source_uri or '', repo=str(repo),
                spec=None if source_uri else dict(ticket.spec), issue=ticket.key,
                model=model, live=False, publish=False, post_worklog=False, language='python',
                layout_mode='existing', max_refine=int(project.config.get('max_refine', 3)),
                max_judge_revisions=int(project.config.get('max_judge_revisions', 2)),
                ledger=ledger, log=emit)
            summary.update(passed=result.passed, iterations=result.iterations,
                           coverage_withdrawn=result.coverage_withdrawn)
        # A semantic-review revision can occur after the native required gate. Verify
        # the final bytes again, without injecting hidden tests or doing extra repair.
        final_started = time.monotonic()
        final_rb = await boundary.behavior_runner().run(path=str(repo))
        ledger.record_deterministic('final_required_behavior', time.monotonic()-final_started)
        if boundary.generated_tests:
            rc, out = await boundary.capture([project.config['python'], '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *boundary.generated_tests], cwd=repo)
            summary['final_generated_tests_pass'] = rc == 0
            summary['final_generated_tests_output'] = out
        else:
            summary['final_generated_tests_pass'] = False
        final_checks = []
        for cmd in project.config['checks']:
            rc, output = await boundary.capture(cmd, cwd=repo)
            final_checks.append({'command': cmd, 'exit': rc, 'output': output})
        boundary.project_checks = final_checks
        summary['passed'] &= summary['final_generated_tests_pass'] and final_rb.passed and bool(final_checks) and all(c['exit'] == 0 for c in final_checks)
        summary['status'] = ('verified_selected_behaviors' if final_rb.items else 'completed_unverified') if summary['passed'] else 'validation_failed'
    except Exception as exc:
        summary.update(passed=False, status='blocked_environment' if boundary.environment_blocked else
                       'budget_exhausted' if 'call cap' in str(exc) else 'validation_failed', error=f'{type(exc).__name__}: {exc}')
    finally:
        summary.update(wall_s=round(time.monotonic()-started, 3), required_behavior=boundary.behavior_results,
                       tests_pass=summary.get('final_generated_tests_pass', boundary.test_results[-1]['passed'] if boundary.test_results else False),
                       project_checks=boundary.project_checks, model_calls_started=calls,
                       stages={k: asdict(v) for k,v in ledger.stages.items()},
                       refines=ledger.stages.get('refine', SimpleNamespace(calls=0)).calls)
        summary['outcome'] = ('initial generated candidate' if summary['refines']==0 else 'autonomous workflow with refinement') if summary['passed'] else summary['status']
        new = sorted(set(Path(calls_root).iterdir())-prior) if Path(calls_root).exists() else []
        summary['call_ids'] = [p.name for p in new if p.is_dir()]
        summary['usage_complete'] = bool(new) and all((p/'usage.json').exists() and json.loads((p/'usage.json').read_text()).get('usage_complete', False) for p in new)
        usages = [json.loads((p/'usage.json').read_text()) for p in new if (p/'usage.json').exists()]
        summary.update(prompt_tokens=sum(u['usage']['input'] for u in usages),
                       completion_tokens=sum(u['usage']['output'] for u in usages),
                       cached_tokens=sum(u['usage']['cached'] for u in usages),
                       cache_write_tokens=sum(u['usage']['cache_write'] for u in usages),
                       calls=sum(u['usage']['requests'] for u in usages), cost_usd=sum(u['cost_usd'] for u in usages))
        if calls and not usages:
            summary.update(prompt_tokens=None, completion_tokens=None, cached_tokens=None, cache_write_tokens=None, cost_usd=None)
        summary['proposed_changes'] = capture_changes(repo, project.config['baseline_commit'], dest)
        (dest/'workflow.log').write_text('\n'.join(logs)+'\n')
        (dest/'VALIDATION.json').write_text(json.dumps({'tests':boundary.test_results,'required_behavior':boundary.behavior_results},indent=2)+'\n')
        (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


def preflight_main():
    import argparse
    import sys

    from project_adapter import ProjectAdapter
    ap = argparse.ArgumentParser(description="Verify pinned native execution and public check inputs; no model calls")
    ap.add_argument('--preflight', action='store_true', required=True)
    ap.add_argument('--project', type=Path, required=True)
    ap.add_argument('--spine-source', type=Path, required=True)
    args = ap.parse_args()
    verify_spine(args.spine_source)
    sys.path.insert(0, str(args.spine_source/'src'))
    project = ProjectAdapter.read(args.project)
    project.verify_target()
    print(json.dumps(protected_files(Path(project.config['target_dir']), project.config)))


if __name__ == '__main__':
    preflight_main()
