"""Spine + PKG — one pass over the tickets on one model, via Spine's own codegen benchmark.

Usage: python spine_pkg.py <model> <pass_no> [--dry-run]
Needs: the provider key for <model> (ANTHROPIC_API_KEY or OPENAI_API_KEY) and ./setup.sh done.

The benchmark (scripts/codegen_benchmark.py) runs unchanged from the Spine version under test
(SPINE_CODE_DIR, default v3.52.0), pointed at the same target commit spec-kit changes
(BENCH_REPO = TARGET_DIR): builds the PKG, designs deterministically, implements, writes tests,
refines, and grades. This wrapper adds, from outside and without editing the repo script:
  * each worktree's generated files are copied out before the benchmark drops it;
  * the repo's CI gate (scripts/state-numbers.py --check) runs in that worktree first;
  * per-ticket wall time, calls and the prompt/completion token split from the benchmark's ledger;
  * one summary.json per ticket, including which tracked files the run changed.
gpt-6-* models go through gpt6_shim (harness-only; see that file).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import harness_config as C

ap = argparse.ArgumentParser()
ap.add_argument("model"); ap.add_argument("pass_no", type=int); ap.add_argument("--dry-run", action="store_true")
A = ap.parse_args()
KEEP = C.RESULTS_DIR / A.model / "spine" / f"pass{A.pass_no}"
os.environ.update(BENCH_REPO=str(C.TARGET_DIR), BENCH_TICKETS=",".join(C.TICKETS),
                  BENCH_DESIGN="deterministic", SDLC_CODEGEN_MODEL=A.model)
if A.dry_run:
    print(f"[dry-run] Spine code {C.SPINE_CODE_DIR} ({C.SPINE_REF}); target {C.TARGET_DIR} @ {C.TARGET_SHA}")
    print(f"[dry-run] model {A.model}; tickets {C.TICKETS}; design deterministic; results {KEEP}")
    print(f"[dry-run] backend: {C.SPINE_BACKEND}; gpt6 API shim: {C.SPINE_BACKEND == 'api' and A.model.startswith('gpt-6')}")
    sys.exit(0)

C.require_project_execution()
C.use_tree(C.SPINE_CODE_DIR)
if C.SPINE_BACKEND == "codex":
    os.environ["CODEX_CALLS_DIR"] = str(KEEP / "codex-calls")
    from codex_llm import install
    install()
elif A.model.startswith("gpt-6"):
    sys.path.insert(0, str(C.HERE))
    import gpt6_shim  # noqa: F401,E402

import codegen_benchmark as cb  # noqa: E402
import heldout_fix  # noqa: E402

HELD_OUT_SUITE = heldout_fix.apply(cb)  # the corrected NEW-DRIFTMD-1 judge; see heldout_fix.py
CUSTOM_CATALOG = C.configure_tickets(cb)
if C.PROJECT:
    C.PROJECT.install(cb)
from scenario_catalog import fingerprint, changed_python_files, split_python_files
SCENARIO_FINGERPRINT = fingerprint(cb.TICKETS)

_drop, _run_ticket = cb.drop_worktree, cb.run_ticket
_gate: dict[str, dict[str, Any]] = {}


def keep_then_drop(path: Path, repo_root: Path = C.TARGET_DIR) -> None:
    status = subprocess.run(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
                            capture_output=True, text=True).stdout.splitlines()
    if C.PROJECT:
        from project_adapter import capture_changes
        snapshot = KEEP / "pending-changes" / path.parent.name
        evidence = capture_changes(path,C.TARGET_SHA,snapshot)
        _gate["last"] = {"status":status,"repo_gate_pass":None,"gate_tail":"not evaluated: token-only",
                         "modified":[],"files":{},"snapshot":str(snapshot),"evidence":evidence,
                         "project_checks":C.PROJECT.checks(path)}
        return
    gate = subprocess.run(["uv", "run", "--frozen", "--project", str(C.SPINE_CODE_DIR), "python",
                           "scripts/state-numbers.py", "--check"], cwd=path, capture_output=True, text=True)
    _gate["last"] = {"status": status, "repo_gate_pass": gate.returncode == 0,
                     "gate_tail": (gate.stdout + gate.stderr)[-600:],
                     "modified": [l[3:] for l in status if l[:2].strip().startswith("M")], "files": {}}
    for line in status:
        rel = line[3:]
        src = path / rel
        if src.is_file() and "__pycache__" not in rel:
            _gate["last"]["files"][rel] = src.read_bytes()
    _drop(path, repo_root)


async def timed_run_ticket(ticket: Any, llm: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
    calls_root = KEEP / "codex-calls"
    prior_calls = set(calls_root.glob("*/usage.json"))
    before = {s: (u.calls, u.prompt_tokens, u.completion_tokens, u.cost_usd) for s, u in llm.ledger.stages.items()}
    _gate.pop("last", None)
    t0 = time.time()
    res = await _run_ticket(ticket, llm, *args, **kwargs)
    wall = round(time.time() - t0, 1)
    stages = {}
    for s, u in llm.ledger.stages.items():
        c0, p0, o0, d0 = before.get(s, (0, 0, 0, 0.0))
        if u.calls - c0:
            stages[s] = {"calls": u.calls - c0, "prompt": u.prompt_tokens - p0,
                         "completion": u.completion_tokens - o0, "cost_usd": round(u.cost_usd - d0, 6)}
    g = _gate.get("last", {})
    dest = KEEP / ticket.key
    for rel, data in g.get("files", {}).items():
        d = dest / "code" / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        d.write_bytes(data)
    out = {**res, "arm": "spine-pkg", "backend": C.SPINE_BACKEND, "codex_auth": C.CODEX_AUTH,
           "model": A.model, "pass": A.pass_no, "spine": C.SPINE_REF, "held_out_suite": HELD_OUT_SUITE,
           "target": C.TARGET_SHA, "wall_s": wall,
           "scenario_fingerprint": SCENARIO_FINGERPRINT, "custom_catalog": CUSTOM_CATALOG, "stages": stages,
           "prompt_tokens": sum(v["prompt"] for v in stages.values()),
           "completion_tokens": sum(v["completion"] for v in stages.values()),
           "calls": sum(v["calls"] for v in stages.values()),
           "repo_gate_pass": g.get("repo_gate_pass"), "gate_tail": g.get("gate_tail"),
           "tracked_files_modified": g.get("modified", []), "git_status": g.get("status", [])}
    if C.SPINE_BACKEND == "codex":
        call_logs = [json.loads(p.read_text()) for p in set(calls_root.glob("*/usage.json")) - prior_calls]
        out.update(
            usage_complete=bool(call_logs) and all(c.get("usage_complete", False) for c in call_logs),
            cost_usd=sum(c["cost_usd"] for c in call_logs),
            prompt_tokens=sum(c["usage"]["input"] for c in call_logs),
            completion_tokens=sum(c["usage"]["output"] for c in call_logs),
            cached_tokens=sum(c["usage"]["cached"] for c in call_logs),
            cache_write_tokens=sum(c["usage"]["cache_write"] for c in call_logs),
            calls=sum(c["usage"]["requests"] for c in call_logs),
        )
    dest.mkdir(parents=True, exist_ok=True)
    if C.PROJECT:
        import shutil
        out.update(evaluation_mode='tokens-only',accepted=None,independent_accepted=None,fit=None,
                   held_out_ran=False,held_out_pass=None,project_checks=g.get('project_checks',[]),
                   proposed_changes=g.get('evidence'))
        if g.get('snapshot'):
            for name in ('changes.patch','CHANGES.md'):
                shutil.copy2(Path(g['snapshot'])/name,dest/name)
    (dest / "summary.json").write_text(json.dumps(out, indent=2, default=str))
    if res.get("aborted"):
        raise RuntimeError(f"Spine infrastructure abort; not a measured result: {dest}")
    print(f"[spine {A.model} {ticket.key}] cost=${out['cost_usd']:.3f} calls={out['calls']} "
          f"in={out['prompt_tokens']} out={out['completion_tokens']} wall={wall}s "
          f"held_out={out.get('held_out_pass')} unrelated_files={len(out['tracked_files_modified'])}", flush=True)
    return res


cb.drop_worktree = keep_then_drop
cb.run_ticket = timed_run_ticket
KEEP.mkdir(parents=True, exist_ok=True)
asyncio.run(cb.main())
