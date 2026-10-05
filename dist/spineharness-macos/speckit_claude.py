"""spec-kit through headless Claude Code — one ticket, one pass.

Usage: python speckit_claude.py <ticket_key> <pass_no> [--model claude-sonnet-5] [--cap 10] [--dry-run]
Needs: ANTHROPIC_API_KEY (Claude Code runs with a throwaway HOME, so API-key billing, not a login),
       `claude` on PATH, and ./setup.sh done (target tree + constitution).

Confinement: HOME is a throwaway directory, no MCP servers are loaded (so spec-kit cannot reach
Spine's graph), and Write/Edit are denied under your real $HOME and the target tree, so spec-kit
can only write inside its own worktree. Every Write/Edit path is audited afterwards from the
session transcript.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import harness_config as C

C.use_tree(C.TARGET_DIR)
import codegen_benchmark as cb  # noqa: E402
import heldout_fix  # noqa: E402

HELD_OUT_SUITE = heldout_fix.apply(cb)  # the corrected NEW-DRIFTMD-1 judge; see heldout_fix.py
CUSTOM_CATALOG = C.configure_tickets(cb)
from scenario_catalog import fingerprint, changed_python_files, split_python_files
SCENARIO_FINGERPRINT = fingerprint(cb.TICKETS)
from orchestrator.evals.graders import run_held_out_tests  # noqa: E402

REAL_HOME = os.path.realpath(os.path.expanduser("~"))


def deny_rules() -> dict:
    paths = {REAL_HOME, os.path.realpath(C.TARGET_DIR), str(C.TARGET_DIR)}
    rules = [f"{verb}(/{p}/**)" for p in sorted(paths) for verb in ("Write", "Edit")]
    return {"permissions": {"deny": rules}}


def sh(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticket"); ap.add_argument("pass_no", type=int)
    ap.add_argument("--model", default="claude-sonnet-5"); ap.add_argument("--cap", type=float, default=10.0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ticket = next(t for t in cb.TICKETS if t.key == a.ticket)
    tag = f"{a.ticket.lower()}-p{a.pass_no}"
    wt, home = C.WORK_DIR / f"speckit-claude-{a.model}-{tag}", C.WORK_DIR / f"home-claude-{a.model}-{tag}"
    out = C.RESULTS_DIR / a.model / "speckit" / tag
    if str(os.path.realpath(C.WORK_DIR)).startswith(REAL_HOME + os.sep):
        raise SystemExit("WORK_DIR is under $HOME, where spec-kit's writes are denied — use e.g. /tmp/speckit-bench")
    constitution = C.RESULTS_DIR / "constitution.md"
    base = ["claude", "-p", "--model", a.model, "--output-format", "json",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--setting-sources", "project", "--dangerously-skip-permissions",
            "--settings", json.dumps(deny_rules())]
    steps = [
        ("01-specify", f"/speckit-specify {C.ticket_text(ticket)}"),
        ("02-clarify", "/speckit-clarify"),
        ("02b-clarify-answer", C.CLARIFY_ANSWER),
        ("03-plan", "/speckit-plan"),
        ("04-checklist", "/speckit-checklist code quality and requirements completeness"),
        ("05-tasks", "/speckit-tasks"),
        ("06-analyze", "/speckit-analyze"),
        ("07-implement", "/speckit-implement"),
        ("08-converge", "/speckit-converge"),
    ]
    if a.dry_run:
        print(f"[dry-run] worktree {wt} @ {C.TARGET_SHA}; results {out}")
        print(f"[dry-run] uvx --from {C.SPECKIT} specify init --here --force --non-interactive --integration claude --script sh")
        for name, prompt in steps:
            print(f"[dry-run] {name}: {' '.join(base[:4])} … {prompt[:70]!r}")
        return
    if not constitution.exists():
        raise SystemExit(f"{constitution} missing — run ./setup.sh (it seeds the constitution once)")
    for p in (wt, home):
        if p.exists():
            raise SystemExit(f"{p} already exists — refusing to reuse a tree (delete it or change RESULTS_DIR)")
    out.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True)

    sh(["git", "worktree", "add", "--detach", str(wt), C.TARGET_SHA], C.SPINE_REPO).check_returncode()
    init = sh(["uvx", "--from", C.SPECKIT, "specify", "init", "--here", "--force", "--non-interactive",
               "--integration", "claude", "--script", "sh"], wt)
    (out / "specify-init.txt").write_text(init.stdout[-3000:] + init.stderr[-3000:])
    shutil.copy2(constitution, wt / ".specify/memory/constitution.md")

    env = dict(os.environ, HOME=str(home), UV_CACHE_DIR=C.UV_CACHE, UV_PYTHON_INSTALL_DIR=C.UV_PYTHON)
    rows, sid, t_start, budget_stop = [], None, time.time(), None
    for name, prompt in steps:
        left = a.cap - sum(r["cost_usd"] for r in rows)
        if left <= 0.5:
            budget_stop = name
            print(f"[{tag}] job cap reached before {name}", flush=True)
            break
        t0 = time.time()
        p = subprocess.run([*base, "--max-budget-usd", f"{left:.2f}", *(["--resume", sid] if sid else []), prompt],
                           cwd=wt, env=env, capture_output=True, text=True, timeout=C.STEP_TIMEOUT_S)
        (out / f"{name}.json").write_text(p.stdout)
        try:
            d = json.loads(p.stdout)
        except json.JSONDecodeError:
            d = {"is_error": True, "result": (p.stdout + p.stderr)[-2000:]}
        u = d.get("usage") or {}
        rows.append({"step": name, "subtype": d.get("subtype"), "is_error": d.get("is_error"),
                     "turns": d.get("num_turns"), "cost_usd": d.get("total_cost_usd") or 0.0,
                     "input": u.get("input_tokens", 0), "cache_write": u.get("cache_creation_input_tokens", 0),
                     "cache_read": u.get("cache_read_input_tokens", 0), "output": u.get("output_tokens", 0),
                     "wall_s": round(time.time() - t0, 1)})
        sid = d.get("session_id") or sid
        print(f"[{tag}] {json.dumps(rows[-1])}", flush=True)
    wall = round(time.time() - t_start, 1)

    status = sh(["git", "status", "--porcelain", "--untracked-files=all"], wt).stdout.splitlines()
    new_py = changed_python_files(wt)
    impl, tests = split_python_files(wt, new_py)
    fit, checks = cb.grade(ticket, new_py, wt)
    modified = [l[3:] for l in status if l[:2].strip().startswith("M")]
    tests_ok, _ = cb.run_pytest(wt, [str(Path(t).relative_to(wt)) for t in tests])
    held = run_held_out_tests(wt, ticket.held_out_tests)

    def uvtool(args: list[str]) -> bool:
        return sh(["uv", "run", "--frozen", "--project", str(C.TARGET_DIR), *args, *impl], wt).returncode == 0

    pre = ({"ruff": uvtool(["ruff", "check"]), "format": uvtool(["ruff", "format", "--check"]),
            "mypy": uvtool(["mypy", "--strict"])} if impl else {"ruff": False, "format": False, "mypy": False})
    gate = sh(["uv", "run", "--frozen", "--project", str(C.TARGET_DIR), "python", "scripts/state-numbers.py", "--check"], wt)
    for rel in [l[3:] for l in status if not l[3:].startswith((".specify/", ".claude/"))]:
        src = wt / rel
        if src.is_file() and "__pycache__" not in rel:
            dst = out / "code" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    (out / "git-status.txt").write_text("\n".join(status) + "\n")

    outside = []
    for tr in home.glob(".claude/projects/*/*.jsonl"):
        for line in tr.read_text().splitlines():
            try:
                m = json.loads(line).get("message", {})
            except json.JSONDecodeError:
                continue
            for b in m.get("content", []) if isinstance(m.get("content"), list) else []:
                if b.get("type") == "tool_use" and b.get("name") in ("Write", "Edit", "NotebookEdit"):
                    fp = b["input"].get("file_path", "")
                    if not (fp.startswith(str(wt)) or fp.startswith(os.path.realpath(wt))):
                        outside.append(fp)
        shutil.copy2(tr, out / f"transcript-{tr.name}")

    tot = {k: sum((r.get(k) or 0) for r in rows) for k in ("turns", "cost_usd", "input", "cache_write", "cache_read", "output")}
    tot["tokens"] = tot["input"] + tot["cache_write"] + tot["cache_read"] + tot["output"]
    tot["requests"] = tot["turns"]
    summary = {
        "arm": "speckit", "agent": "claude-code", "ticket": a.ticket, "kind": ticket.kind, "pass": a.pass_no,
               "scenario_fingerprint": SCENARIO_FINGERPRINT, "custom_catalog": CUSTOM_CATALOG, "model": a.model,
        "target": C.TARGET_SHA, "speckit": C.SPECKIT.rsplit("@", 1)[1], "wall_s": wall, "rows": rows, "total": tot,
        "stopped_at_job_cap_before": budget_stop, "reached_code": bool(impl),
        "grading": {"impl_files": [str(Path(p).relative_to(wt)) for p in impl],
                    "test_files": [str(Path(p).relative_to(wt)) for p in tests],
                    "fit": fit, "fit_checks": checks, "own_tests_pass": tests_ok,
                    "held_out_ran": held.ran, "held_out_suite": HELD_OUT_SUITE, "held_out_pass": held.passed, "preflight": pre,
                    "repo_gate_pass": gate.returncode == 0, "tracked_files_modified": modified},
        "writes_outside_worktree": outside, "worktree": str(wt),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[{tag}] DONE cost=${tot['cost_usd']:.2f} turns={tot['turns']} held_out={held.passed} "
          f"gate={gate.returncode == 0} outside={len(outside)}", flush=True)


if __name__ == "__main__":
    main()
