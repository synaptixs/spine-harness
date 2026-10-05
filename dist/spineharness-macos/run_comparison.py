#!/usr/bin/env python3
"""Run spec-kit and Spine + PKG on the same tickets, models and commit, with a soft budget.

  ./run_comparison.py --dry-run --models claude-sonnet-5 --passes 1        # what would run; no spend
  ./run_comparison.py --models claude-sonnet-5 --passes 3 --cap 60         # the published Claude run
  ./run_comparison.py --models gpt-5.6-sol,gpt-6-astra --passes 2 --cap 150  # the published OpenAI run
  ./run_comparison.py --models gpt-5.6-sol --arms spine --passes 2         # re-measure only Spine

claude-* models drive spec-kit through Claude Code; gpt-* models through the Codex CLI. Each pass
runs every ticket through spec-kit (in parallel) plus Spine + PKG and its intake step. A pass only
starts if the money already spent plus that pass's reserve fits under --cap; the first quota
error writes RESULTS_DIR/QUOTA_STOP and every job stops. Then: ./summarize.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import harness_config as C

# Measured cost of one spec-kit run per model (USD), used only to reserve budget before a pass.
SPECKIT_RESERVE = {"claude-sonnet-5": 6.0, "gpt-5.6-sol": 8.0, "gpt-6-astra": 16.0}
SPINE_RESERVE = 1.0  # a whole Spine + PKG pass on one model, all tickets, measured well under this


def spent() -> float:
    total = 0.0
    for p in C.RESULTS_DIR.glob("*/speckit/*/summary.json"):
        total += json.loads(p.read_text())["total"]["cost_usd"]
    for p in C.RESULTS_DIR.glob("*/spine/pass*/*/summary.json"):
        total += json.loads(p.read_text()).get("cost_usd") or 0.0
    for p in C.RESULTS_DIR.glob("*/intake/pass*.json"):
        total += sum(r["cost_usd"] for r in json.loads(p.read_text()))
    return total


def py(script: str, *args: str) -> list[str]:
    return ["uv", "run", "--frozen", "--project", str(C.SPINE_CODE_DIR), "python", str(C.HERE / script), *args]


def run(cmd: list[str], log: Path, dry: bool) -> None:
    if not dry and (C.RESULTS_DIR / "JOB_FAILED").exists():
        raise RuntimeError("Earlier job failed; inspect JOB_FAILED before restarting")
    log.parent.mkdir(parents=True, exist_ok=True)
    if dry:
        subprocess.run([*cmd, "--dry-run"], cwd=C.HERE, check=True)
        return
    with open(log, "w") as f:
        proc = subprocess.run(cmd, cwd=C.HERE, stdout=f, stderr=subprocess.STDOUT)
    text = log.read_text(errors="replace").lower()
    if any(m in text for m in C.QUOTA_MARKERS) and not C.STOP.exists():
        C.STOP.write_text(f"quota error in {log}\n")
    if proc.returncode:
        (C.RESULTS_DIR / "JOB_FAILED").write_text(f"exit {proc.returncode}: {log}\n")
        raise RuntimeError(f"Job failed (exit {proc.returncode}); inspect {log}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", required=True, help="comma-separated, e.g. claude-sonnet-5,gpt-5.6-sol")
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--arms", default="speckit,spine", help="speckit, spine, or both")
    ap.add_argument("--cap", type=float, default=600.0, help="pass admission budget in equivalent USD; may overshoot")
    ap.add_argument("--job-cap", type=float, default=None, help="per spec-kit run cap in USD")
    ap.add_argument("--parallel", type=int, default=3, help="spec-kit runs at once (lower it if you hit rate limits)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--approve-checklist", action="store_true",
                    help="Operator explicitly approves Codex implementation with unchecked reviewer checklist items")
    a = ap.parse_args()
    if C.PROJECT and not a.dry_run:
        C.require_project_execution()
    models, arms = a.models.split(","), set(a.arms.split(","))
    if a.passes < 1 or a.cap <= 0 or (a.job_cap is not None and a.job_cap <= 0):
        ap.error('Passes and budgets must be positive')
    if not arms or not arms <= {'speckit','spine'} or len(set(models)) != len(models):
        ap.error('Use unique model IDs and arms speckit,spine')
    from codex_usage import PRICES
    if C.PROJECT and any(not m.startswith('gpt-') for m in models):
        ap.error('Project adapter currently supports the two Codex workflows only')
    for m in models:
        if not m or '/' in m or '\\' in m or m in ('.','..'):
            ap.error('Invalid model ID')
        if m.startswith('gpt') and m not in PRICES:
            ap.error(f'No verified price for {m}; add official rates to codex_usage.py first')
    # Validate both pinned catalogs before admitting any model work. This also
    # rejects unknown IDs instead of silently running fewer Spine tickets.
    catalogs = []
    for tree in ('target','spine'):
        result = subprocess.run(py('scenarios.py','snapshot','--tree',tree), cwd=C.HERE, text=True, capture_output=True)
        if result.returncode:
            sys.exit(result.stderr or result.stdout)
        catalogs.append(json.loads(result.stdout))
    if catalogs[0]['scenario_fingerprint'] != catalogs[1]['scenario_fingerprint']:
        sys.exit('Target and Spine scenario/judge definitions differ; resolve before running')
    for key in ('EVAL_TASKSET','EVAL_SKILL','BENCH_ALL','BENCH_NO_GROUNDING'):
        if os.environ.get(key):
            sys.exit(f'Unset {key}; it changes the matched comparison protocol')
    if C.CODEX_AUTH == "app" and any(not m.startswith("claude") for m in models):
        if "spine" in arms and C.SPINE_BACKEND != "codex" and not os.environ.get("OPENAI_API_KEY"):
            sys.exit("CODEX_AUTH=app signs in spec-kit's Codex runs only. Spine + PKG calls OpenAI's API "
                     "directly and needs OPENAI_API_KEY; without one, run spec-kit alone: --arms speckit")
        if a.parallel > 1:
            # Every run shares one sign-in; one at a time keeps concurrent runs from racing on it.
            print(f"CODEX_AUTH=app: running one job at a time (--parallel {a.parallel} ignored)")
            a.parallel = 1
    C.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if C.STOP.exists():
        sys.exit(f"{C.STOP} exists ({C.STOP.read_text().strip()}) — fix the quota, delete it, re-run")
    if (C.RESULTS_DIR / "JOB_FAILED").exists() and not a.dry_run:
        sys.exit("JOB_FAILED exists; diagnose it, then select fresh WORK_DIR and RESULTS_DIR")
    if not a.dry_run:
        if (C.RESULTS_DIR/'EXPERIMENT.json').exists() or any(C.RESULTS_DIR.glob('*/logs/*.log')):
            sys.exit('Existing experiment output; select fresh WORK_DIR and RESULTS_DIR. No general resume is supported.')
        meta = {**catalogs[0], 'models':models, 'passes':a.passes,'arms':sorted(arms),
                'created_utc':datetime.now(timezone.utc).isoformat(),
                'model_reasoning_effort':C.CODEX_REASONING_EFFORT,'codex_auth':C.CODEX_AUTH,
                'target':C.TARGET_SHA,'spine_ref':C.SPINE_REF,'speckit':C.SPECKIT,
                'checklist_approval':a.approve_checklist,'cap':a.cap,'job_cap':a.job_cap,
                'order':'fixed serial in subscription mode','intake':'separately measured; not fed into codegen'}
        if C.PROJECT:
            meta['project'] = C.PROJECT.config
            meta['evaluation_mode'] = 'tokens-only'
            meta['intake'] = 'shared deterministic Jira normalization; zero model calls; no separate Spine intake'
        meta['target_commit'] = subprocess.check_output(['git','-C',str(C.TARGET_DIR),'rev-parse','HEAD'],text=True).strip()
        meta['spine_commit'] = subprocess.check_output(['git','-C',str(C.SPINE_CODE_DIR),'rev-parse','HEAD'],text=True).strip()
        meta['uv_version'] = subprocess.check_output(['uv','--version'],text=True).strip()
        if any(not m.startswith('claude') for m in models):
            meta['codex_cli'] = subprocess.check_output(['codex','--version'],text=True).strip()
        (C.RESULTS_DIR/'EXPERIMENT.json').write_text(json.dumps(meta,indent=2)+'\n')
    for n in range(1, a.passes + 1):
        reserve = sum(SPECKIT_RESERVE.get(m, 16.0) * len(C.TICKETS) for m in models if "speckit" in arms)
        reserve += SPINE_RESERVE * len(models) * ("spine" in arms)
        if not a.dry_run and spent() + reserve > a.cap:
            print(f"cap: pass {n} not started (spent ${spent():.2f}, reserve ${reserve:.2f}, cap ${a.cap:.2f})")
            break
        if C.STOP.exists():
            print(f"quota stop: pass {n} not started")
            break
        jobs = []
        with ThreadPoolExecutor(max_workers=max(1, a.parallel)) as pool:
            for m in models:
                if "speckit" in arms:
                    for key in C.TICKETS:
                        tag = f"{key.lower()}-p{n}"
                        if m.startswith("claude"):
                            cmd = py("speckit_claude.py", key, str(n), "--model", m)
                        else:
                            cmd = py("speckit_codex.py", m, key, str(n))
                            if a.approve_checklist:
                                cmd += ["--approve-checklist"]
                        if a.job_cap:
                            cmd += ["--cap", str(a.job_cap)]
                        jobs.append(pool.submit(run, cmd, C.RESULTS_DIR / m / "logs" / f"speckit-{tag}.log", a.dry_run))
                if "spine" in arms:
                    jobs.append(pool.submit(run, py("spine_pkg.py", m, str(n)),
                                            C.RESULTS_DIR / m / "logs" / f"spine-p{n}.log", a.dry_run))
                    if not C.PROJECT:
                        jobs.append(pool.submit(run, py("spine_intake.py", m, str(n)),
                                                C.RESULTS_DIR / m / "logs" / f"intake-p{n}.log", a.dry_run))
            for j in jobs:
                j.result()
        print(f"pass {n} done — spent so far ${spent():.2f}", flush=True)
    print("next: python3 report_results.py --results \"$RESULTS_DIR\"" if not a.dry_run else "dry run only — nothing was spent")


if __name__ == "__main__":
    main()
