#!/usr/bin/env python3
"""Finalize the already-running study after its runner reports pass 3 closed.

This is a local continuation of the current batch, not a new model run. It never
restarts, repairs, or changes benchmark worktrees or the frozen harness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE / 'results/study-20260929'


def load(p):
    return json.loads(p.read_text())


def ready():
    for name in ('JOB_FAILED', 'QUOTA_STOP'):
        if (ROOT / name).exists():
            raise RuntimeError(f'Batch stopped: {name}: {(ROOT / name).read_text()}')
    log = ROOT / 'batch.log'
    return log.exists() and 'pass 3 done' in log.read_text()


def finalize():
    from report_usage import summarize_usage

    protocol = load(ROOT / 'PROTOCOL.json')
    model = protocol['model']
    expected = {(ticket, n) for ticket in protocol['tickets'] for n in range(1, protocol['passes'] + 1)}
    paths = {
        'speckit': sorted((ROOT / model).glob('speckit/*/summary.json')),
        'spine': sorted((ROOT / model).glob('spine/pass*/*/summary.json')),
    }
    arms = {arm: [load(p) for p in files] for arm, files in paths.items()}
    intake = [r for p in sorted((ROOT / model).glob('intake/pass*.json')) for r in load(p)]
    errors = []
    for arm, rows in {**arms, 'intake': intake}.items():
        keys = [(r['ticket'], r['pass']) for r in rows]
        if len(keys) != len(set(keys)) or set(keys) != expected:
            errors.append(f'{arm}: missing, unexpected, or duplicate ticket/pass keys')
    for name, digest in protocol['source_sha256'].items():
        if hashlib.sha256((ROOT / 'harness_snapshot' / name).read_bytes()).hexdigest() != digest:
            errors.append(f'Frozen source hash changed: {name}')
    planning = {}
    for r in arms['speckit']:
        if r.get('model') != model or r.get('reasoning_effort') != protocol['reasoning_effort'] or r.get('codex_auth') != 'app':
            errors.append(f"Model/settings mismatch: {r['ticket']} pass {r['pass']}")
        feature = Path(r['worktree']) / '.specify/feature.json'
        directory = load(feature).get('feature_directory') if feature.exists() else None
        planning[f"{r['ticket']}/pass{r['pass']}"] = directory
        if not directory:
            errors.append(f'Missing planning directory: {feature}')
    if len(set(planning.values())) != len(planning):
        errors.append('Planning directory reused between runs')
    for r in arms['spine']:
        if r.get('model') != model or r.get('codex_auth') != 'app' or not r.get('usage_complete', False):
            errors.append(f"Spine metadata/usage issue: {r['ticket']} pass {r['pass']}")

    usage = summarize_usage(ROOT)
    summary_cost = sum(r['total']['cost_usd'] for r in arms['speckit']) + sum(r['cost_usd'] for r in arms['spine']) + sum(r['cost_usd'] for r in intake)
    recorded_cost = sum(r['cost_usd'] for r in usage['models'].values() if r['cost_usd'] is not None)
    if abs(summary_cost - recorded_cost) > .01:
        errors.append('Summary cost differs from exported response ledger by more than USD0.01; inspect failed/retried calls')

    closed = datetime.now(timezone.utc).isoformat()
    analysis = ROOT / 'analysis'
    analysis.mkdir(exist_ok=True)
    analysis_hashes = {}
    for name in ('build_comparison_report.py', 'report_usage.py', 'codex_usage.py', 'finalize_study.py'):
        shutil.copy2(HERE / name, analysis / name)
        analysis_hashes[name] = hashlib.sha256((analysis / name).read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(analysis / 'build_comparison_report.py'), '--results', str(ROOT), '--model', model], check=True)
    result = subprocess.run([
        sys.executable, str(HERE / 'measure_closed_run.py'), '--model', model, '--measured-only',
        '--since', '2026-09-29T13:49:00Z', '--until', closed,
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (ROOT / 'tokens-and-cost.txt').write_text(result.stdout)
    if result.returncode:
        errors.append(f'Shared calculator exited {result.returncode}')
    audit = {'closed_utc': closed, 'expected_per_arm': len(expected), 'rows_per_arm': {k: len(v) for k, v in arms.items()},
             'intake_rows': len(intake), 'planning_directories': planning,
             'capacity_recoveries': sum(bool(r.get('capacity_recovery')) for r in arms['speckit']),
             'summary_cost_usd': summary_cost, 'exported_ledger_cost_usd': recorded_cost,
             'analysis_sha256': analysis_hashes, 'errors': errors,
             'status': 'automated checks passed; narrative review pending' if not errors else 'review required'}
    (ROOT / 'FINALIZATION.json').write_text(json.dumps(audit, indent=2) + '\n')
    report = ROOT / 'COMPARISON_REPORT.md'
    body = report.read_text().replace(
        'Final accounting must be regenerated after all child sessions close and reconciled with the shared session calculator.',
        'Accounting was regenerated after the batch finished. The shared calculator output is in `tokens-and-cost.txt`; '
        'automated verification and the closed window are in `FINALIZATION.json`. Narrative review remains pending.')
    if errors:
        body = '**Review required:** ' + '; '.join(errors) + '\n\n' + body
    report.write_text(body)
    archive = ROOT / 'comparison-results.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        candidates = [report, ROOT / 'PROTOCOL.json', ROOT / 'FINALIZATION.json', ROOT / 'recorded-usage.json', ROOT / 'tokens-and-cost.txt']
        candidates += list(analysis.glob('*.py'))
        candidates += [p for files in paths.values() for p in files]
        candidates += list((ROOT / model).glob('intake/pass*.json'))
        if (ROOT / 'CAPACITY_RECOVERY.json').exists():
            candidates += [ROOT / 'CAPACITY_RECOVERY.json', ROOT / 'capacity_recovery_snapshot/speckit_codex.py']
        for p in candidates:
            z.write(p, p.relative_to(ROOT))
    print(json.dumps(audit, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Show readiness without writing or waiting')
    args = parser.parse_args()
    if args.check:
        print(json.dumps({'ready': ready()}))
        return
    try:
        deadline = time.monotonic() + 24 * 3600
        while not ready():
            if time.monotonic() >= deadline:
                raise TimeoutError('No completion marker within 24 hours; benchmark was not altered')
            time.sleep(30)
        finalize()
    except Exception as exc:
        (ROOT / 'FINALIZATION_FAILED.txt').write_text(f'{type(exc).__name__}: {exc}\n')
        raise


if __name__ == '__main__':
    main()
