#!/usr/bin/env python3
"""Prepare an external-repository benchmark without executing models."""
from __future__ import annotations

import argparse
import json
import shlex
from datetime import UTC, datetime
from pathlib import Path

from project_adapter import capture_changes, disposable_clone, git, source_fingerprint

CONSTITUTION='''# Benchmark implementation principles

Implement the frozen issue requirements using this repository's existing conventions and types.
Preserve public behavior outside the requested change. Add focused tests for changed behavior.
Work only in the disposable repository copy and designated planning directory.
Never contact Jira, push commits, open pull requests, or change external services.
Do not edit requirements or evaluation records to make a failing implementation appear successful.
Report incomplete work and failed checks explicitly. Do not claim tests passed unless executed.
'''


def prepare(profile, source, spine_code, work, results, python, catalog=None):
    profile=json.loads(Path(profile).read_text());source=Path(source).resolve();spine_code=Path(spine_code).resolve()
    work=Path(work).resolve();results=Path(results).resolve()
    if work.exists() or results.exists():raise ValueError('Use fresh WORK_DIR and RESULTS_DIR; existing output is preserved')
    if work.is_relative_to(source) or results.is_relative_to(source):raise ValueError('Work/results must be outside source repository')
    if not (spine_code/'scripts/codegen_benchmark.py').is_file():raise ValueError('Spine implementation checkout missing')
    before=source_fingerprint(source)
    sha=disposable_clone(source,work/'target',profile['baseline_commit'])
    results.mkdir(parents=True)
    preparation_base = sha
    if profile.get('behavior_files'):
        for relative, source_file in profile['behavior_files'].items():
            rel = Path(relative)
            if rel.is_absolute() or '..' in rel.parts or '.git' in rel.parts:
                raise ValueError('behavior_files destinations must be safe repository-relative paths')
            dest = work/'target'/rel
            if dest.exists() or dest.is_symlink() or not dest.resolve().is_relative_to(work/'target'):
                raise ValueError('behavior_files may only add new files inside the disposable baseline')
            src = Path(source_file)
            if src.is_symlink() or not src.is_file():
                raise ValueError('behavior_files source must be a regular file')
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
        capture_changes(work/'target', sha, results/'public-behavior-preparation')
        git(work/'target', 'add', '-A')
        git(work/'target', '-c', 'user.name=Benchmark', '-c', 'user.email=benchmark@example.invalid',
            'commit', '-m', 'Prepare common public behavior checks')
        sha = git(work/'target', 'rev-parse', 'HEAD').decode().strip()
        profile['behavior_protected_files'] = sorted(set(profile.get('behavior_protected_files', [])) | set(profile['behavior_files']))
    profile.pop('behavior_files', None)
    config={**profile,'source_repo':str(source),'baseline_commit':sha,'target_dir':str(work/'target'),
            'python':str(Path(python).absolute()),'baseline_reviewed':False}
    (results/'PROJECT.json').write_text(json.dumps(config,indent=2)+'\n')
    (results/'constitution.md').write_text(CONSTITUTION)
    state={'created_utc':datetime.now(UTC).isoformat(),'source_before':before,
           'unmodified_baseline_commit':preparation_base,'source_after':source_fingerprint(source),'model_execution':'disabled',
           'baseline_note':'Candidate committed baseline; review against actual Jira issue before execution.'}
    (results/'PREPARATION.json').write_text(json.dumps(state,indent=2)+'\n')
    env={'PROJECT_CONFIG':str(results/'PROJECT.json'),'SPINE_REPO':str(spine_code),'SPINE_CODE_DIR':str(spine_code),
         'WORK_DIR':str(work),'TARGET_DIR':str(work/'target'),'TARGET_SHA':sha,'RESULTS_DIR':str(results),
         'CODEX_AUTH':'app','SPINE_BACKEND':'codex','MODEL':'gpt-6-sol','CODEX_REASONING_EFFORT':'high',
         'CODEX_OUTPUT_MODE':'envelope','CODEX_LOGIN_HOME':str(work/'codex-login'),
         'UV_CACHE_DIR':str(work/'uv-cache'),'BENCHMARK_EXECUTE':'0'}
    if catalog:
        catalog=Path(catalog).resolve();data=json.loads(catalog.read_text())
        env.update(SCENARIO_FILE=str(catalog),TICKETS=','.join(r['key'] for r in data['scenarios']))
    else:
        env.update(SCENARIO_FILE=str(results/'jira/scenarios.json'),TICKETS='UNSELECTED-0')
    (results/'benchmark.env').write_text('# Source from the harness directory. Preparation never authorizes model execution.\n'+
        '\n'.join(f'export {k}={shlex.quote(v)}' for k,v in env.items())+
        '\nunset OPENAI_API_KEY ANTHROPIC_API_KEY CODEX_API_KEY CODEX_ACCESS_TOKEN\n')
    (results/'PREPARATION.md').write_text(f'''# External repository benchmark preparation

- Repository: {profile['repository_url']}
- Jira: {profile['jira_url']} — project {profile['jira_project']}
- Candidate baseline: `{sha}`
- Original working files and Git metadata unchanged: **{state['source_before']==state['source_after']}**
- Disposable target has no Git remotes; uncommitted source changes were not copied.
- Model execution: **disabled**. No measured results exist.

Next: import full Jira issue keys, review the frozen requirements and baseline, set SCENARIO_FILE/TICKETS,
configure a dedicated application Python environment and appropriate checks, and validate both catalogs.
Live execution additionally requires baseline_reviewed in PROJECT.json, a matching reviewed REVIEW.json,
and an explicit BENCHMARK_EXECUTE=1. Do not enable it until a benchmark run is requested.
''')
    return results/'PREPARATION.md'


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile',required=True,type=Path);ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--spine-code',required=True,type=Path);ap.add_argument('--work-dir',required=True,type=Path)
    ap.add_argument('--results',required=True,type=Path);ap.add_argument('--python',required=True)
    ap.add_argument('--catalog',type=Path)
    a=ap.parse_args();print(prepare(a.profile,a.source,a.spine_code,a.work_dir,a.results,a.python,a.catalog))


if __name__=='__main__':main()
