#!/usr/bin/env python3
"""Build the macOS or Windows/WSL2 Jira handover from reviewed source/result allowlists."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '2026-10-04-v7'
NAME = 'spineharness-macos'
CORE = ('harness_config.py run_comparison.py speckit_codex.py speckit_claude.py spine_pkg.py spine_intake.py '
        'codex_llm.py codex_protocol.py codex_usage.py gpt6_shim.py heldout_fix.py constitution.md '
        'summarize.py report_usage.py scenario_catalog.py scenarios.py report_results.py model_report.py '
        'jira_import.py project_adapter.py project_benchmark.py report_project.py '
        'test_codex_backend.py test_report_usage.py test_scenarios.py test_jira_benchmark.py wsl_support.py test_wsl_support.py').split()
PORTABLE = ('benchmark.py deliverables.py benchmark.example.json README.md QUICKSTART.md CONFIGURATION.md AGENTS.md VALIDATION.md test_portable.py').split()
STUDIES = ('ontm4-benchmark-20260930', 'ontm4-spine-recovery-20260930', 'ontm4-spine-resumed-20261004', 'ontm4-spine-continuation-20261004')
REF_ROOT = {'COMPARISON_REPORT.md','CONTINUATION_REPORT.md','CONTINUATION_VALIDATION.md','CONTINUATION_VERIFICATION.json',
    'ARTIFACT_COMPARISON.md','RESULTS.md','FINALIZATION.json','READING_THE_RESULTS.md','INDEPENDENT_REVIEW.md',
    'STAGE_TOKEN_BREAKDOWN.json','EVIDENCE_VERIFICATION.json','SUPPLEMENTAL_VALIDATION.md','SUPPLEMENTAL_VALIDATION.json',
    'PRICING_VERIFICATION.json','PREPARATION.md','PROTOCOL_AMENDMENT.json','PREPARATION.json','PROJECT.json','EXPERIMENT.json',
    'BASELINE_MANIFEST.json','BASELINE_CHECKS.json','BASELINE_CHECKS.log','PREREQUISITE.patch','application-requirements.lock',
    'recorded-usage.json','calculator-usage.json','tokens-and-cost.txt','response-ledger.json','summary.json','USAGE.json',
    'FEEDBACK.txt','DESIGN_SETUP.json','MODEL_OUTPUT_HASHES.json','CALCULATOR_PROVENANCE.json','SHARED_CALCULATOR.json',
    'STARTED','FINISHED','EXIT_CODE','RESUMPTION.json','RECOVERY_PLAN.json','CALL_BOUND.json','continuation.log'}
SECRET = re.compile(rb'\bsk-[A-Za-z0-9_-]{20,}|\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"(?:access_token|refresh_token|id_token)"\s*:\s*"[^"\s]{16,}"')

def safe_copy(source, dest, historical=False):
    if source.is_symlink(): raise ValueError('Symlink in release input: ' + str(source))
    data = source.read_bytes()
    if SECRET.search(data): raise ValueError('Possible credential in ' + str(source))
    if historical and source.suffix in ('.json','.md','.log','.txt','.xml'):
        # Preserve patches/generated source exactly; redact historical machine-local locations in narrative/metadata.
        text = data.decode('utf-8')
        text = text.replace(str(ROOT), '__HARNESS__').replace('/Users/falcon', '__AUTHOR_HOME__')
        text = text.replace('/private/tmp/', '__HOST_TMP__/').replace('/var/folders/', '__HOST_CACHE__/')
        data = text.encode()
    dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(data)

def reference_files(stage):
    if (ROOT / 'reference').is_dir():
        for p in (ROOT / 'reference').rglob('*'):
            if p.is_file(): safe_copy(p, stage / p.relative_to(ROOT))
        return
    manifest = []
    for name in STUDIES:
        source = ROOT / 'results' / name
        for p in sorted(source.rglob('*')):
            if not p.is_file() or p.is_symlink(): continue
            rel = p.relative_to(source)
            include = len(rel.parts) == 1 and p.name in REF_ROOT
            if rel.parts[0] == 'acceptance_audit' and p.suffix in ('.json','.log','.xml') or (rel.parts[0] == 'acceptance_audit' and p.name == 'test_ontm4_surfaces.py'): include = True
            if rel.parts[0] in ('incremental-changes','cumulative-changes','refine-1') and p.suffix in ('.json','.md','.patch'): include = True
            if rel.parts[0] == 'jira' and p.suffix == '.json': include = True
            if rel.parts[0] == 'gpt-6-sol':
                if p.name in ('summary.json','usage.json','CHANGES.md','changes.patch','git-status.txt','EXECUTION.json','INCOMPLETE.txt'): include = True
                if 'planning' in rel.parts and p.suffix in ('.md','.json'): include = True
                if 'code' in rel.parts and p.suffix in ('.py','.md','.json'): include = True
                if 'logs' in rel.parts and p.suffix == '.log': include = True
            if name.endswith('continuation-20261004') and rel.parts[0] == 'codex-calls' and p.name == 'usage.json': include = True
            if name.endswith('continuation-20261004') and p.name.startswith('spine-continuation.') and p.suffix in ('.json','.log','.xml'): include = True
            if not include: continue
            dest = stage / 'reference/results' / name / rel
            safe_copy(p, dest, historical=True)
            manifest.append({'file': str(dest.relative_to(stage)), 'original_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                             'exported_sha256': hashlib.sha256(dest.read_bytes()).hexdigest(),
                             'historical_path_redaction': p.read_bytes() != dest.read_bytes()})
    (stage / 'reference/EXPORT_MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (stage / 'reference/README.md').write_text('''# Completed ONTM-4 case study

Start with [the final comparison report](results/ontm4-benchmark-20260930/COMPARISON_REPORT.md).

This evidence includes the post-audit continuation, first-run failures, selected validation, proposed patches and usage ledgers. It is not a reusable task catalog for unrelated projects. The final implementations both pass the seven selected checks, but Spine received audit feedback; this is not evidence of equal overall quality or an unbiased protocol comparison.

Narrative/JSON/log exports replace author-machine paths with __HARNESS__, __AUTHOR_HOME__, __HOST_TMP__ or __HOST_CACHE__. Those are historical locations, not configuration to copy. Exported patches and generated source are byte-preserved. EXPORT_MANIFEST.json records original and exported hashes. Full raw model conversations, credentials, old launchers and machine-specific finalizers are omitted. The root deliverables.py generates new portable reports and archives.

The response-only ledger retains recorded token usage. Four earlier interrupted calls have unknown consumption. No zero-cost substitution is made. Supervision is separate.
''')

def build(output, platform='macos'):
    release_name = 'spineharness-windows-wsl2' if platform == 'windows' else NAME
    version = '2026-10-04-v8' if platform == 'windows' else VERSION
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'{release_name}-{version}.zip'
    with tempfile.TemporaryDirectory(prefix='spineharness-release-') as t:
        stage = Path(t) / release_name; stage.mkdir()
        for name in CORE: safe_copy(ROOT / name, stage / name)
        for name in PORTABLE: safe_copy((ROOT / 'portable' / name) if (ROOT / 'portable').is_dir() else ROOT / name, stage / name)
        if platform == 'windows':
            overlay = ROOT / 'portable_windows'
            for file in overlay.iterdir() if overlay.is_dir() else []:
                if file.is_file() and file.suffix in ('.md', '.ps1', '.py', '.json'): safe_copy(file, stage / file.name)
            if not overlay.is_dir():
                for filename in ('Run-Harness.ps1', 'verify_package.py', 'wsl_entry.py', 'SETUP_WSL.md'):
                    safe_copy(ROOT / filename, stage / filename)
        safe_copy(Path(__file__), stage / 'build_portable_release.py')
        for folder in ('catalog','examples'):
            for p in (ROOT / folder).rglob('*'):
                if p.is_file() and p.suffix in ('.py','.json','.md'): safe_copy(p, stage / p.relative_to(ROOT))
        (stage / '.gitignore').write_text('.local/\n.env*\nbenchmark.json\ninputs/\nresults/\n__pycache__/\n*.pyc\n.venv/\ndist/\n')
        reference_files(stage)
        report = stage / 'reference/results/ontm4-benchmark-20260930/COMPARISON_REPORT.md'
        (stage / 'FINAL_REFERENCE_REPORT.html').write_text('<!doctype html><meta charset="utf-8"><title>ONTM-4 final reference report</title><style>body{max-width:1100px;margin:3em auto;padding:0 2em;font:16px system-ui;color:#172033}pre{white-space:pre-wrap;font:15px/1.6 system-ui}</style><h1>Completed ONTM-4 reference study</h1><p>Original failures and the post-audit continuation are preserved. See the Markdown report and reference/results for linked artifacts.</p><pre>'+html.escape(report.read_text())+'</pre>')
        hashes = {}
        for p in sorted(stage.rglob('*')):
            if not p.is_file(): continue
            data = p.read_bytes(); rel = str(p.relative_to(stage))
            if SECRET.search(data): raise ValueError('Credential-like material in final package: ' + rel)
            if not rel.startswith('reference/') and p.name != 'build_portable_release.py' and any(x in data for x in (b'/Users/falcon', b'/private/tmp/spineharness-')):
                raise ValueError('Nonportable operational file: ' + rel)
            hashes[rel] = hashlib.sha256(data).hexdigest()
        manifest = {'name': release_name, 'version': version, 'platform': 'Windows via WSL2 Ubuntu' if platform == 'windows' else 'macOS',
                    'native_windows_execution': False, 'application_check_sandbox': 'bubblewrap' if platform == 'windows' else 'sandbox-exec', 'application_language': 'Python',
                    'spine_commit': '6c0454bac2dbb539665402d31e57e763db2d206a', 'speckit_ref': 'v1.0.11',
                    'default_model': 'gpt-6-sol', 'reasoning': 'high', 'spine_timeout_seconds': 2700,
                    'includes_reference_results': True, 'includes_credentials': False, 'includes_raw_conversations': False,
                    'includes_spine_repository': False, 'includes_generated_application_artifacts': True, 'sha256': hashes}
        (stage / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
        hashes['MANIFEST.json'] = hashlib.sha256((stage / 'MANIFEST.json').read_bytes()).hexdigest()
        (stage / 'SHA256SUMS').write_text(''.join(f'{h}  {p}\n' for p,h in sorted(hashes.items())))
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(stage.rglob('*')):
                if p.is_file(): z.write(p, str(Path(release_name) / p.relative_to(stage)))
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None: raise ValueError('Archive CRC failure')
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(checksum + '  ' + archive.name + '\n')
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': checksum}, indent=2))
    return archive

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'dist')
    p.add_argument('--platform', choices=['macos', 'windows'], default='windows' if (ROOT/'Run-Harness.ps1').exists() else 'macos')
    args = p.parse_args(); build(args.output.resolve(), args.platform)
