#!/usr/bin/env python3
"""One recorded capacity recovery, then only the unstarted jobs in their original order."""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / 'results/study-20260929'
FROZEN = ROOT / 'harness_snapshot'
RECOVERY = ROOT / 'capacity_recovery_snapshot'
MODEL = 'gpt-6-sol'


def run(script, args, log, fresh=True):
    if fresh and log.exists():
        raise RuntimeError(f'Refusing to overwrite job log: {log}')
    cmd = ['uv', 'run', '--frozen', '--project', str(Path(os.environ['WORK_DIR']) / 'spine-code'),
           'python', str(script), *args]
    with log.open('x' if fresh else 'a') as f:
        result = subprocess.run(cmd, cwd=script.parent, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Exit {result.returncode}: {log}')


def spent():
    total = 0.0
    for p in (ROOT / MODEL).glob('speckit/*/summary.json'):
        total += json.loads(p.read_text())['total']['cost_usd']
    for p in (ROOT / MODEL).glob('spine/pass*/*/summary.json'):
        total += json.loads(p.read_text())['cost_usd']
    for p in (ROOT / MODEL).glob('intake/pass*.json'):
        total += sum(r['cost_usd'] for r in json.loads(p.read_text()))
    return total


def main():
    with (ROOT / 'CAPACITY_CONTINUATION_STARTED').open('x') as f:
        f.write('One bounded same-model recovery; no duplicate launch.\n')
    logs = ROOT / MODEL / 'logs'
    try:
        run(RECOVERY / 'speckit_codex.py', [MODEL, 'NEW-DRIFTMD-1', '2', '--cap', '20', '--resume-capacity', '--approve-checklist'],
            logs / 'speckit-new-driftmd-1-p2-capacity-recovery.log')
        summary = json.loads((ROOT / MODEL / 'speckit/new-driftmd-1-p2/summary.json').read_text())
        if not summary.get('reached_code') or summary.get('stopped_at_job_cap_before'):
            raise RuntimeError('Recovery did not finish implementation within its budget')
        evidence = ROOT / 'capacity-interruption-20260929'
        for name in ('JOB_FAILED', 'FINALIZATION_FAILED.txt', 'finalization.log'):
            p = ROOT / name
            if p.exists():
                p.rename(evidence / ('closed-' + name))
        with (ROOT / 'finalization.log').open('w') as f:
            subprocess.Popen([sys.executable, str(HERE / 'finalize_study.py')], cwd=HERE, stdout=f, stderr=subprocess.STDOUT)
        with (ROOT / 'batch.log').open('a') as batch:
            batch.write('\nCapacity recovery completed on the same model/thread; original failure preserved in capacity-interruption-20260929.\n')
            batch.flush()
            for n in (2, 3):
                if n == 3:
                    if spent() + 49 > 200:
                        raise RuntimeError('Original pass-admission cap prevents pass 3')
                    for ticket in ('NEW-SEVSUMMARY-1', 'NEW-LEDGERMD-1', 'NEW-DRIFTMD-1'):
                        run(FROZEN / 'speckit_codex.py', [MODEL, ticket, str(n), '--cap', '20', '--approve-checklist'],
                            logs / f'speckit-{ticket.lower()}-p{n}.log')
                for script, label in (('spine_pkg.py', 'spine'), ('spine_intake.py', 'intake')):
                    run(FROZEN / script, [MODEL, str(n)], logs / f'{label}-p{n}.log')
                batch.write(f'pass {n} done — spent so far ${spent():.2f}\n')
                batch.flush()
    except Exception as exc:
        (ROOT / 'CAPACITY_CONTINUATION_FAILED.txt').write_text(f'{type(exc).__name__}: {exc}\n')
        if not (ROOT / 'JOB_FAILED').exists():
            (ROOT / 'JOB_FAILED').write_text(f'Capacity continuation stopped: {exc}\n')
        raise


if __name__ == '__main__':
    main()
