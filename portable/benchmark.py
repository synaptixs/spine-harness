#!/usr/bin/env python3
"""macOS / Windows-with-WSL2 Jira benchmark entry point. No model call until the explicit run command."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SPINE_COMMIT = '6c0454bac2dbb539665402d31e57e763db2d206a'
SPINE_URL = 'https://github.com/synaptixs/spine.git'

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')

def now():
    return datetime.now(timezone.utc).isoformat()

def load_config(path):
    path = path.resolve()
    c = json.loads(path.read_text(encoding='utf-8-sig'))
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', c['name']):
        raise ValueError('name must contain only letters, numbers, underscores or hyphens')
    def absolute(value):
        if re.match(r'^[A-Za-z]:[\\/]', value) or value.startswith('\\\\'):
            raise ValueError('Use Linux/WSL paths in benchmark.json, e.g. /mnt/c/code/app or /home/me/code/app')
        p = Path(os.path.expandvars(value)).expanduser()
        return str((path.parent / p).resolve() if not p.is_absolute() else p.resolve())
    c['source_repo'] = absolute(c['source_repo'])
    c['work_dir'] = absolute(c.get('work_dir', str(Path(tempfile.gettempdir()) / ('spineharness-' + c['name']))))
    c['results_dir'] = absolute(c.get('results_dir', 'results/' + c['name']))
    default_tools = '~/.local/share/spineharness/spine-tools-' + SPINE_COMMIT[:12] if sys.platform == 'linux' else '.local/spine-tools'
    c['tools_dir'] = absolute(c.get('tools_dir', default_tools))
    c['login_home'] = absolute(c.get('login_home', '~/.codex-spineharness'))
    if c.get('application_python'):
        if re.match(r'^[A-Za-z]:[\\/]', c['application_python']) or c['application_python'].startswith('\\\\') or c['application_python'].lower().endswith('.exe'):
            raise ValueError('application_python must be a Linux/WSL interpreter, not Windows Python')
        # Preserve a venv's interpreter symlink: resolving it would select the base Python.
        p = Path(os.path.expandvars(c['application_python'])).expanduser()
        c['application_python'] = str((path.parent / p).absolute() if not p.is_absolute() else p.absolute())
    c['snapshots'] = [absolute(p) for p in c.get('snapshots', [])]
    if c.get('mcp_config'):
        c['mcp_config'] = absolute(c['mcp_config'])
    c['acceptance_tests'] = {k: [absolute(p) for p in paths] for k, paths in c.get('acceptance_tests', {}).items()}
    from jira_import import KEY
    if not c.get('issues') or any(not KEY.fullmatch(k) for k in c['issues']) or len(set(c['issues'])) != len(c['issues']):
        raise ValueError('issues must contain unique full Jira keys, e.g. TEAM-123')
    source, work, results, login, tools = map(Path, (c['source_repo'], c['work_dir'], c['results_dir'], c['login_home'], c['tools_dir']))
    for p in (work, results, tools, login):
        if p == source or p.is_relative_to(source):
            raise ValueError('Work, results, tools and login directories must be outside the source repository')
    for first, second in ((work, results), (login, results), (login, work), (tools, results), (tools, work)):
        if first.is_relative_to(second) or second.is_relative_to(first):
            raise ValueError('Work, results, tools and credential directories must be separate')
    if work.is_relative_to(Path.home().resolve()):
        raise ValueError('Use a disposable work_dir under /tmp, outside the home directory')
    if not c.get('checks') or any(not isinstance(cmd, list) or not cmd or any(not isinstance(x, str) for x in cmd) for cmd in c['checks']):
        raise ValueError('Provide at least one offline project check as an argv array')
    c.setdefault('model', 'gpt-6-sol')
    c.setdefault('passes', 1)
    c.setdefault('cap', 150)
    c.setdefault('job_cap', 150)
    c.setdefault('reasoning_effort', 'high')
    c.setdefault('completion_timeout_seconds', 2700)
    return c

def prerequisites():
    if sys.platform not in ('darwin', 'linux'):
        raise RuntimeError('On Windows use Run-Harness.ps1 through WSL2, not Windows Python')
    sandbox = 'bwrap' if sys.platform == 'linux' else 'sandbox-exec'
    missing = [x for x in ('git', 'uv', 'uvx', 'codex', sandbox) if not shutil.which(x)]
    if missing:
        raise RuntimeError('Install missing prerequisites: ' + ', '.join(missing) + '; see QUICKSTART.md')
    if sys.platform == 'linux':
        for name in ('git', 'uv', 'uvx', 'codex'):
            executable = Path(shutil.which(name)).resolve()
            if str(executable).startswith('/mnt/') or executable.suffix.lower() == '.exe':
                raise RuntimeError('Install the Linux version of ' + name + ' inside Ubuntu; Windows executables are not supported')

def tool_python(c):
    return str(Path(c['tools_dir']) / '.venv/bin/python')

def bootstrap(c, spine_source):
    prerequisites()
    dest = Path(c['tools_dir'])
    if dest.exists():
        head = subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip()
        if head != SPINE_COMMIT:
            raise ValueError('Existing tools directory has another version; select a new tools_dir')
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--no-hardlinks', '--no-checkout', spine_source or SPINE_URL, str(dest)], check=True)
        subprocess.run(['git', '-C', str(dest), 'checkout', '--detach', SPINE_COMMIT], check=True)
    subprocess.run(['uv', 'sync', '--frozen', '--python', '3.12', '--extra', 'dev', '--extra', 'mcp'], cwd=dest, check=True)
    print('Tools ready. Run the login command once with your own ChatGPT account.')

def login(c, device_auth=False):
    prerequisites()
    p = Path(c['login_home']); p.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = dict(os.environ, CODEX_HOME=str(p))
    command = ['codex', '-c', 'cli_auth_credentials_store="file"', 'login']
    if device_auth: command.append('--device-auth')
    subprocess.run(command, env=env, check=True)

def prepare(c):
    prerequisites()
    from project_benchmark import prepare as prepare_project
    from project_adapter import ProjectAdapter, git
    from jira_import import save_import, unwrap
    results, work = Path(c['results_dir']), Path(c['work_dir'])
    if results.exists() or work.exists():
        raise ValueError('Existing work/results preserved. Choose a NEW name (and fresh paths if overridden).')
    if not Path(tool_python(c)).exists():
        raise ValueError('Run bootstrap first')
    snapshot_issues = [unwrap(json.loads(Path(p).read_text(encoding='utf-8-sig'))) for p in c['snapshots']]
    if snapshot_issues and {i['key'] for i in snapshot_issues} != set(c['issues']):
        raise ValueError('Snapshot issue keys do not exactly match the configured issues')
    if not snapshot_issues and not (c.get('mcp_config') and c.get('mcp_server')):
        raise ValueError('Save Jira read-tool responses in snapshots, or configure mcp_config + mcp_server')
    app_python = c.get('application_python', str(work / 'app-venv/bin/python'))
    profile = {k: c[k] for k in ('repository_url', 'jira_url', 'checks')}
    profile.update(jira_project=c['issues'][0].split('-')[0], baseline_commit=c.get('baseline', 'HEAD'),
                   source_paths=c.get('source_paths', ['.', 'src']))
    with tempfile.TemporaryDirectory(prefix='harness-profile-') as t:
        pp = Path(t) / 'profile.json'; write(pp, profile)
        prepare_project(pp, c['source_repo'], c['tools_dir'], work, results, app_python)
    project_path = results / 'PROJECT.json'
    project = json.loads(project_path.read_text()); project['python'] = app_python
    write(project_path, project)
    if not c.get('application_python'):
        subprocess.run(['uv', 'venv', '--python', '3.12', str(work / 'app-venv')], check=True)
        argv = ['uv', 'pip', 'install', '--python', app_python, 'pytest']
        for rel in c.get('requirements_files', []):
            p = (work / 'target' / rel).resolve()
            if not p.is_relative_to(work / 'target') or not p.is_file():
                raise ValueError('requirements_files must exist inside the prepared target')
            argv += ['-r', str(p)]
        argv += c.get('extra_test_packages', [])
        subprocess.run(argv, cwd=work / 'target', check=True)
        if c.get('install_project', False):
            subprocess.run(['uv', 'pip', 'install', '--python', app_python, '-e', str(work / 'target')], check=True)
    if snapshot_issues:
        save_import(snapshot_issues, results / 'jira', c['jira_url'], c.get('acceptance_field'))
    else:
        argv = [tool_python(c), str(ROOT / 'jira_import.py'), '--keys', ','.join(c['issues']),
                '--jira-url', c['jira_url'], '--mcp-config', c['mcp_config'], '--server', c['mcp_server'],
                '--output', str(results / 'jira')]
        if c.get('acceptance_field'): argv += ['--acceptance-field', c['acceptance_field']]
        subprocess.run(argv, cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(Path(c['tools_dir']) / 'src')), check=True)
    audit_files = {}
    for key, files in c['acceptance_tests'].items():
        if key not in c['issues']: raise ValueError('Acceptance test key not selected')
        audit_files[key] = []
        for index, source in enumerate(files):
            p = Path(source)
            if not p.name.startswith('test_') or p.suffix != '.py': raise ValueError('Acceptance tests must be test_*.py files')
            target = results / 'acceptance-tests' / key / str(index) / p.name
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)
            audit_files[key].append({'path': str(target.relative_to(results)), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    adapter = ProjectAdapter.read(results / 'PROJECT.json')
    adapter.verify_execution_sandbox()
    checks = adapter.checks(work / 'target')
    write(results / 'BASELINE_CHECKS.json', checks)
    env = make_env(c)
    subprocess.run([tool_python(c), str(ROOT / 'scenarios.py'), 'validate'], cwd=ROOT, env=env, check=True)
    # No credentials/config values from the Jira transport are persisted here.
    public = {k: v for k, v in c.items() if k not in ('mcp_config', 'mcp_server', 'snapshots')}
    write(results / 'RUN_CONFIG.json', public)
    write(results / 'ACCEPTANCE_TESTS.json', audit_files)
    write(results / 'PREPARED.json', {'utc': now(), 'baseline_checks_pass': all(x.get('exit') == 0 for x in checks),
                                     'config_sha256': config_digest(c), 'model_execution': 'not started'})
    print(f'Prepared {results}. Inspect frozen Jira requirements and BASELINE_CHECKS.json before run.')
    if not all(x.get('exit') == 0 for x in checks):
        raise RuntimeError('Baseline checks failed. Fix preparation in a NEW run; do not benchmark a broken baseline silently.')

def config_digest(c):
    return hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest()

def make_env(c):
    results, work = Path(c['results_dir']), Path(c['work_dir'])
    env = dict(os.environ)
    for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN',
                'EVAL_TASKSET', 'EVAL_SKILL', 'BENCH_ALL', 'BENCH_NO_GROUNDING', 'PROJECT_CONFIG'):
        env.pop(key, None)
    env.update(PROJECT_CONFIG=str(results / 'PROJECT.json'), SPINE_REPO=c['tools_dir'], SPINE_CODE_DIR=c['tools_dir'],
               WORK_DIR=str(work), RESULTS_DIR=str(results), TARGET_DIR=str(work / 'target'),
               SPINE_REF='v3.52.0', CODEX_AUTH='app', SPINE_BACKEND='codex', CODEX_LOGIN_HOME=c['login_home'],
               SCENARIO_FILE=str(results / 'jira/scenarios.json'), TICKETS=','.join(c['issues']), MODEL=c['model'],
               CODEX_REASONING_EFFORT=c['reasoning_effort'], CODEX_OUTPUT_MODE='envelope',
               CODEX_COMPLETION_TIMEOUT_S=str(c['completion_timeout_seconds']), BENCHMARK_EXECUTE='0',
               UV_CACHE_DIR=str(work / 'uv-cache'))
    return env

def run(c, approved, checklist):
    if not approved:
        raise ValueError('Use --approved only after reviewing the prepared baseline and authorizing selected Jira text/code transfer to OpenAI')
    prerequisites()
    from project_adapter import ProjectAdapter, source_fingerprint
    results = Path(c['results_dir']); prepared = json.loads((results / 'PREPARED.json').read_text())
    if prepared['config_sha256'] != config_digest(c): raise ValueError('Config changed after preparation; prepare a fresh run')
    if not prepared['baseline_checks_pass']: raise ValueError('Baseline checks did not pass')
    if (results / 'STARTED').exists(): raise ValueError('Run already started; preserve it and choose a new run name')
    initial_source = source_fingerprint(c['source_repo'])
    expected_source = json.loads((results / 'PREPARATION.json').read_text())['source_before']
    if initial_source != expected_source: raise ValueError('Source checkout changed since preparation; prepare a fresh run')
    env = make_env(c)
    subprocess.run(['codex', 'login', 'status'], env=dict(env, CODEX_HOME=c['login_home']), check=True, stdout=subprocess.DEVNULL)
    project_path = results / 'PROJECT.json'; project = json.loads(project_path.read_text())
    project['baseline_reviewed'] = True; write(project_path, project)
    review_path = results / 'jira/REVIEW.json'; review = json.loads(review_path.read_text())
    review.update(reviewed=True, reviewed_utc=now()); write(review_path, review)
    write(results / 'AUTHORIZATION.json', {'utc': now(), 'data_transfer_approved': True, 'baseline_reviewed': True,
                                          'unchecked_checklist_continuation_approved': checklist})
    (results / 'STARTED').write_text(now() + '\n')
    write(results / 'RUNNING.json', {'pid': os.getpid(), 'started': now()})
    env['BENCHMARK_EXECUTE'] = '1'
    command = [tool_python(c), str(ROOT / 'run_comparison.py'), '--models', c['model'], '--passes', str(c['passes']),
               '--parallel', '1', '--cap', str(c['cap']), '--job-cap', str(c['job_cap'])]
    if checklist: command.append('--approve-checklist')
    code = 1
    try:
        with (results / 'batch.log').open('w') as log:
            code = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    except (OSError, KeyboardInterrupt) as exc:
        code = 130 if isinstance(exc, KeyboardInterrupt) else 1
        (results / 'RUN_ERROR.txt').write_text(str(exc) or 'Interrupted by operator')
    finally:
        try:
            after = source_fingerprint(c['source_repo'])
            write(results / 'SOURCE_VERIFICATION.json', {'unchanged': after == initial_source, 'before': initial_source, 'after': after})
        except Exception as exc:
            write(results / 'SOURCE_VERIFICATION.json', {'unchanged': None, 'error': str(exc)})
        (results / 'EXIT_CODE').write_text(str(code) + '\n')
        (results / 'FINISHED').write_text(now() + '\n')
        (results / 'RUNNING.json').unlink(missing_ok=True)
    from deliverables import finalize
    finalize(results, run_audits=True)
    print(f'Run exit {code}. Final report and artifacts: {results / "deliverables"}')
    return code

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['doctor', 'bootstrap', 'login', 'prepare', 'run', 'report'])
    p.add_argument('--config', type=Path, default=ROOT / 'benchmark.json')
    p.add_argument('--spine-source', help='Authorized Spine checkout or repository URL; default pinned repository')
    p.add_argument('--device-auth', action='store_true', help='Use device sign-in, useful from WSL')
    p.add_argument('--approved', action='store_true')
    p.add_argument('--approve-checklist', action='store_true')
    a = p.parse_args()
    if a.action == 'doctor':
        prerequisites()
        if sys.platform == 'linux':
            from wsl_support import verify_linux_sandbox
            verify_linux_sandbox()
        print('Prerequisites found; no model calls made.'); return 0
    c = load_config(a.config)
    if a.action == 'bootstrap': bootstrap(c, a.spine_source)
    elif a.action == 'login': login(c, a.device_auth)
    elif a.action == 'prepare': prepare(c)
    elif a.action == 'run': return run(c, a.approved, a.approve_checklist)
    elif a.action == 'report':
        from deliverables import finalize
        finalize(Path(c['results_dir']), run_audits=False)
    return 0

if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
