"""spec-kit through headless Codex CLI — one ticket, one pass, one model.

Usage: python speckit_codex.py <model> <ticket_key> <pass_no> [--cap 20] [--dry-run]
Needs: OPENAI_API_KEY, `codex` on PATH, and ./setup.sh done (target tree + constitution).

Your own Codex setup is never touched: every run gets a throwaway CODEX_HOME and logs in there
with OPENAI_API_KEY, so the Codex app's login, config and history stay as they are.

With CODEX_AUTH=app, runs sign in with a ChatGPT account instead (the Codex app's subscription):
every run uses one harness-only sign-in home, CODEX_LOGIN_HOME, logged in once by hand. Usage is
still read from Codex's own per-request records, filtered to this run's worktree, and cost is the
same list-price computation, so it is comparable with API-key runs; your plan is not billed per
token. Still never ~/.codex.

Differences from the Claude Code arm, all forced by the agent, none by choice:
  * spec-kit is initialised with `--integration codex` (skills in .agents/skills, invoked `$name`);
  * CLAUDE.md is copied to AGENTS.md in the throwaway worktree, so both agents get the same
    repository instructions;
  * confinement is Codex's own sandbox (`workspace-write`: writes only inside the worktree, plus
    uv's cache so tests can run); network allowed, as it was for the Claude arm;
  * Codex reports tokens, not dollars: cost = plain input × input rate + cache writes × write rate
    + cache reads × read rate + output × output rate, from litellm's price catalog;
  * Checklist gates pause unless --approve-checklist records explicit user authorization;
    an authorized continuation is recorded as step 07b.
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
import codegen_benchmark as cb

import heldout_fix

HELD_OUT_SUITE = heldout_fix.apply(cb)  # the corrected NEW-DRIFTMD-1 judge; see heldout_fix.py
CUSTOM_CATALOG = C.configure_tickets(cb)
if C.PROJECT:
    C.PROJECT.install(cb)
from scenario_catalog import changed_python_files, fingerprint, split_python_files

SCENARIO_FINGERPRINT = fingerprint(cb.TICKETS)
from orchestrator.evals.graders import run_held_out_tests

from codex_protocol import needs_checklist_approval
from codex_usage import PRICE_BASIS, rates, run_sessions, session_usage


def sh(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 600, stdin: str | None = None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout, input=stdin)


_PROJECT_RUN = None

def main() -> None:
    global _PROJECT_RUN
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("ticket"); ap.add_argument("pass_no", type=int)
    ap.add_argument("--cap", type=float, default=20.0); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume-checklist", action="store_true", help="Resume a saved app-mode run paused at the checklist gate")
    ap.add_argument("--resume-capacity", action="store_true", help="Resume one preserved implementation interrupted by model capacity")
    ap.add_argument("--approve-checklist", action="store_true", help="Use only after the user explicitly approves proceeding with unchecked checklist items")
    a = ap.parse_args()
    if C.PROJECT and not a.dry_run:
        C.require_project_execution()
    if a.resume_capacity and (a.resume_checklist or not a.approve_checklist):
        ap.error("--resume-capacity requires --approve-checklist and excludes --resume-checklist")
    if a.resume_checklist and not a.approve_checklist:
        ap.error("--resume-checklist requires explicit user approval and --approve-checklist")
    ticket = next(t for t in cb.TICKETS if t.key == a.ticket)
    tag = f"{a.ticket.lower()}-p{a.pass_no}"
    wt, home = C.WORK_DIR / f"speckit-codex-{a.model}-{tag}", C.WORK_DIR / f"codex-home-{a.model}-{tag}"
    app = C.CODEX_AUTH == "app"
    if app:
        home = C.CODEX_LOGIN_HOME
    scope = wt if app else None  # a shared sign-in home: count only this run's sessions
    out = C.RESULTS_DIR / a.model / "speckit" / tag
    if C.PROJECT and not a.dry_run:
        _PROJECT_RUN = (wt, out, home, scope)
    constitution = C.RESULTS_DIR / "constitution.md"
    feature_directory = C.WORK_DIR / "specifications" / a.model / tag
    writable_roots = [str(C.UV_CACHE)]
    if C.PROJECT:
        writable_roots.append(str(feature_directory))
        if not a.dry_run:
            feature_directory.mkdir(parents=True, exist_ok=True)
    sandbox = ["-c", 'sandbox_mode="workspace-write"', "-c",
               "sandbox_workspace_write.network_access=" + ("false" if C.PROJECT else "true"),
               "-c", 'sandbox_workspace_write.writable_roots=' + json.dumps(writable_roots)]
    common = ["--json", "-m", a.model, "--skip-git-repo-check", "--ignore-user-config",
              "--disable", "multi_agent", "--disable", "apps", "--disable", "plugins",
              "-c", f'model_reasoning_effort="{C.CODEX_REASONING_EFFORT}"', *sandbox]
    if app:
        common += ["-c", 'forced_login_method="chatgpt"']
    steps = [
        ("01-specify", f"$speckit-specify {C.ticket_text(ticket)}"),
        ("02-clarify", "$speckit-clarify"),
        ("02b-clarify-answer", C.CLARIFY_ANSWER),
        ("03-plan", "$speckit-plan"),
        ("04-checklist", "$speckit-checklist code quality and requirements completeness"),
        ("05-tasks", "$speckit-tasks"),
        ("06-analyze", "$speckit-analyze"),
        ("07-implement", "$speckit-implement"),
        ("08-converge", "$speckit-converge"),
    ]
    previous = None
    if a.resume_capacity:
        if not app:
            raise SystemExit("Capacity recovery requires CODEX_AUTH=app")
        previous = json.loads((out / "capacity-checkpoint.json").read_text())
        if (previous["model"], previous["ticket"], previous["pass"], previous["worktree"]) != (a.model, a.ticket, a.pass_no, str(wt)):
            raise SystemExit("Capacity checkpoint does not match requested run")
        last = previous["rows"][-1]
        if last["step"] != "07b-implement-proceed" or "Selected model is at capacity" not in (last.get("error") or ""):
            raise SystemExit("Only the preserved implementation capacity interruption can be recovered")
        if (out / "07c-capacity-resume.jsonl").exists() or (out / "summary.json").exists():
            raise SystemExit("Recovery was already attempted; preserve and inspect its results")
        steps = [("07c-capacity-resume", "Continue the implementation step interrupted by model capacity. Resume from the current working tree and finish the planned tasks and verification. The existing approval to proceed despite unchecked checklist items still applies."),
                 ("08-converge", "$speckit-converge")]
    if a.resume_checklist:
        if not app:
            raise SystemExit("Checklist recovery currently requires CODEX_AUTH=app")
        previous = json.loads((out / "summary.json").read_text())
        if previous["model"] != a.model or previous["ticket"] != a.ticket or previous["worktree"] != str(wt):
            raise SystemExit("Saved run does not match this model, ticket and worktree")
        if previous["reached_code"] or not any(needs_checklist_approval(r.get("last_message_tail", "")) for r in previous["rows"]):
            raise SystemExit("Saved run is not an unimplemented checklist pause")
        if (out / "summary.before-checklist-recovery.json").exists():
            raise SystemExit("Checklist recovery was already attempted; inspect its logs")
        steps = [("07b-implement-proceed", "Yes, proceed with implementation despite the unchecked code-quality checklist. Execute the planned tasks."),
                 ("08-converge", "$speckit-converge")]
    if a.dry_run:
        print(f"[dry-run] worktree {wt} @ {C.TARGET_SHA}; CODEX_HOME {home} (sign-in: {C.CODEX_AUTH}); results {out}")
        print(f"[dry-run] uvx --from {C.SPECKIT} specify init --here --force --non-interactive --integration codex --script sh --ignore-agent-tools")
        for name, prompt in steps:
            print(f"[dry-run] {name}: codex exec {' '.join(common[:3])} … {prompt[:70]!r}")
        return
    if not constitution.exists():
        raise SystemExit(f"{constitution} missing — run ./setup.sh (it seeds the constitution once)")
    for p in (() if previous else ((wt,) if app else (wt, home))):
        if p.exists():
            raise SystemExit(f"{p} already exists — refusing to reuse a tree (choose a fresh WORK_DIR and RESULTS_DIR)")
    out.mkdir(parents=True, exist_ok=True)
    if app:
        env = dict(C.codex_env(), CODEX_HOME=str(home))
        if C.PROJECT:
            env['PATH'] = str(Path(C.PROJECT.config['python']).parent) + os.pathsep + env.get('PATH', '')
        if sh(["codex", "login", "status"], C.SPINE_REPO, env).returncode:
            raise SystemExit(f"CODEX_AUTH=app but {home} is not signed in — run once: "
                             f"CODEX_HOME={home} codex login")
    else:
        home.mkdir(parents=True)
        env = dict(C.codex_env(), CODEX_HOME=str(home))
        if sh(["codex", "login", "--with-api-key"], C.SPINE_REPO, env, stdin=os.environ["OPENAI_API_KEY"]).returncode:
            raise SystemExit("codex login failed — check OPENAI_API_KEY")

    if not previous:
        # The target requires new planning documents outside its checkout. Give
        # each repeat a separate directory so no run reuses another run's plan.
        env["SPECIFY_INIT_DIR"] = str(wt)
        env["SPECIFY_FEATURE_DIRECTORY"] = str(C.WORK_DIR / "specifications" / a.model / tag)
        if C.PROJECT:
            from project_adapter import disposable_clone
            disposable_clone(C.TARGET_DIR, wt, C.TARGET_SHA)
        else:
            sh(["git", "worktree", "add", "--detach", str(wt), C.TARGET_SHA], C.SPINE_REPO).check_returncode()
        init = sh(["uvx", "--from", C.SPECKIT, "specify", "init", "--here", "--force", "--non-interactive",
                   "--integration", "codex", "--script", "sh", "--ignore-agent-tools"], wt)
        (out / "specify-init.txt").write_text(init.stdout[-3000:] + init.stderr[-3000:])
        init.check_returncode()
        shutil.copy2(constitution, wt / ".specify/memory/constitution.md")
        if (wt / "CLAUDE.md").exists() and not (wt / "AGENTS.md").exists():
            shutil.copy2(wt / "CLAUDE.md", wt / "AGENTS.md")
    elif not a.resume_capacity:
        shutil.copy2(out / "summary.json", out / "summary.before-checklist-recovery.json")
        for suffix in (".jsonl", ".stderr.txt"):
            path = out / ("08-converge" + suffix)
            if path.exists():
                path.rename(out / ("08a-converge-before-approval" + suffix))
        for row in previous["rows"]:
            if row["step"] == "08-converge":
                row["step"] = "08a-converge-before-approval"

    pi, po, pr, pw = rates(a.model)
    if a.resume_capacity:
        env["SPECIFY_INIT_DIR"] = str(wt)
        env["SPECIFY_FEATURE_DIRECTORY"] = str(C.WORK_DIR / "specifications" / a.model / tag)
    rows = list(previous["rows"]) if previous else []
    thread = previous["thread"] if previous else None
    t_start, budget_stop, checklist_pause = time.time(), None, False
    prev = session_usage(home, scope)
    queue = list(steps)
    while queue:
        name, prompt = queue.pop(0)
        if C.STOP.exists():
            budget_stop = f"QUOTA_STOP before {name}"
            break
        if sum(r["cost_usd"] for r in rows) >= a.cap:
            budget_stop = name
            break
        cmd = ["codex", "exec", *(["resume", thread] if thread else []), *common, prompt]
        t0 = time.time()
        p = subprocess.run(cmd, cwd=wt, env=env, capture_output=True, text=True, timeout=C.STEP_TIMEOUT_S,
                           stdin=subprocess.DEVNULL)
        (out / f"{name}.jsonl").write_text(p.stdout)
        if p.stderr:
            (out / f"{name}.stderr.txt").write_text(p.stderr[-20000:])
        turns, last_msg, err = 0, "", None
        for line in p.stdout.splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") == "thread.started":
                thread = thread or d.get("thread_id")
            if d.get("type") in ("turn.failed", "error"):
                err = json.dumps(d)[:500]
            if d.get("type") == "item.completed":
                it = d.get("item", {})
                if it.get("type") in ("command_execution", "file_change", "mcp_tool_call", "web_search"):
                    turns += 1
                if it.get("type") == "agent_message":
                    last_msg = it.get("text", "")
        now = session_usage(home, scope)
        u = {k: now[k] - prev[k] for k in now}
        prev = now
        plain = max(u["input"] - u["cached"] - u["cache_write"], 0)
        cost = plain * pi + u["cache_write"] * pw + u["cached"] * pr + u["output"] * po
        rows.append({"step": name, "tool_actions": turns, "cost_usd": round(cost, 6), **u,
                     "wall_s": round(time.time() - t0, 1), "error": err, "exit": p.returncode,
                     "last_message_tail": last_msg[-400:]})
        print(f"[{tag}] {json.dumps({k: v for k, v in rows[-1].items() if k != 'last_message_tail'})}", flush=True)
        if err and any(m in err.lower() for m in C.QUOTA_MARKERS):
            C.STOP.write_text(f"{a.model} {tag} {name}: {err}\n")
            budget_stop = f"QUOTA_STOP at {name}"
            break
        if p.returncode or not any(json.loads(l).get("type") == "turn.completed"
                                   for l in p.stdout.splitlines() if l.startswith("{")):
            raise RuntimeError(f"Codex step {name} failed; see {out}")
        if not u["requests"]:
            raise RuntimeError(f"Missing per-response token records for {name}; see {out}")
        if name == "07-implement" and needs_checklist_approval(last_msg):
            if a.approve_checklist:
                queue.insert(0, ("07b-implement-proceed", "yes, proceed with implementation despite the unchecked checklist items."))
            else:
                checklist_pause = True
                break
    wall = round((previous["wall_s"] if previous else 0) + time.time() - t_start, 1)

    status = sh(["git", "status", "--porcelain", "--untracked-files=all"], wt).stdout.splitlines()
    skip = (".specify/", ".agents/", "specs/", "AGENTS.md")
    new_py = changed_python_files(wt)
    impl, tests = split_python_files(wt, new_py)
    fit, checks = cb.grade(ticket, new_py, wt)
    modified = [l[3:] for l in status if l[:2].strip().startswith("M")]
    tests_ok, _ = cb.run_pytest(wt, [str(Path(t).relative_to(wt)) for t in tests])
    held = run_held_out_tests(wt, ticket.held_out_tests)

    def uvtool(args: list[str]) -> bool:
        return sh(["uv", "run", "--frozen", "--project", str(C.TARGET_DIR), *args, *impl], wt).returncode == 0

    pre = ({"ruff": uvtool(["ruff", "check"]), "format": uvtool(["ruff", "format", "--check"]),
            "mypy": uvtool(["mypy", "--strict"])} if impl and not C.PROJECT else {"ruff": False, "format": False, "mypy": False})
    if C.PROJECT:
        from types import SimpleNamespace
        project_checks = C.PROJECT.checks(wt)
        pre = {}
        gate = SimpleNamespace(returncode=None)
    else:
        project_checks = []
        gate = sh(["uv", "run", "--frozen", "--project", str(C.TARGET_DIR), "python", "scripts/state-numbers.py", "--check"], wt)
    for rel in [l[3:] for l in status if not l[3:].startswith((".specify/", ".agents/"))]:
        src = wt / rel
        if src.is_file() and "__pycache__" not in rel and rel != "AGENTS.md":
            dst = out / "code" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    (out / "git-status.txt").write_text("\n".join(status) + "\n")
    for s in run_sessions(home, scope):
        shutil.copy2(s, out / f"session-{s.name}")
    feature_state = wt / ".specify/feature.json"
    if feature_state.exists():
        feature_dir = Path(json.loads(feature_state.read_text())["feature_directory"])
        if not feature_dir.is_absolute():
            feature_dir = wt / feature_dir
        if feature_dir.is_dir():
            shutil.copytree(feature_dir, out / "planning", dirs_exist_ok=True)

    keys = ("cost_usd", "input", "cached", "cache_write", "output", "reasoning", "requests", "tool_actions")
    tot = {k: sum((r.get(k) or 0) for r in rows) for k in keys}
    tot["tokens"] = tot["input"] + tot["output"]
    summary = {"arm": "speckit", "agent": "codex", "model": a.model, "ticket": a.ticket, "kind": ticket.kind, "pass": a.pass_no,
               "scenario_fingerprint": SCENARIO_FINGERPRINT, "custom_catalog": CUSTOM_CATALOG,
               "target": C.TARGET_SHA, "speckit": C.SPECKIT.rsplit("@", 1)[1],
               "codex": sh(["codex", "--version"], C.SPINE_REPO).stdout.strip(),
               # cost_usd is list price from Codex's token records in both modes; "app" is not billed per token
               "codex_auth": C.CODEX_AUTH, "price_basis": PRICE_BASIS,
               "reasoning_effort": C.CODEX_REASONING_EFFORT, "checklist_recovery": a.resume_checklist,
               "capacity_recovery": a.resume_capacity,
               "recovered_steps": {"07b-implement-proceed": "07c-capacity-resume"} if a.resume_capacity else {},
               "checklist_approval": a.approve_checklist, "paused_for_checklist": checklist_pause,
               "wall_s": wall, "rows": rows, "total": tot, "stopped_at_job_cap_before": budget_stop,
               "reached_code": bool(impl), "thread": thread,
               "grading": {"impl_files": [str(Path(p).relative_to(wt)) for p in impl],
                           "test_files": [str(Path(p).relative_to(wt)) for p in tests],
                           "fit": fit, "fit_checks": checks, "own_tests_pass": tests_ok,
                           "held_out_ran": held.ran, "held_out_suite": HELD_OUT_SUITE, "held_out_pass": held.passed, "preflight": pre,
                           "repo_gate_pass": gate.returncode == 0, "tracked_files_modified": modified},
               "worktree": str(wt)}
    if C.PROJECT:
        from project_adapter import capture_changes
        summary['proposed_changes'] = capture_changes(wt,C.TARGET_SHA,out)
        summary['evaluation_mode'] = 'tokens-only'
        summary['project_checks'] = project_checks
        summary['grading'].update(fit=None, fit_checks={}, held_out_pass=None, held_out_ran=False, repo_gate_pass=None)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"[{tag}] DONE cost=${tot['cost_usd']:.2f} tokens_in={tot['input']:,} cached={tot['cached']:,} "
          f"out={tot['output']:,} held_out={held.passed} gate={gate.returncode == 0}", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        if _PROJECT_RUN:
            wt, out, home, scope = _PROJECT_RUN
            out.mkdir(parents=True, exist_ok=True)
            for session in run_sessions(home, scope):
                shutil.copy2(session, out / f"session-{session.name}")
            if (wt / '.git').exists():
                from project_adapter import capture_changes
                capture_changes(wt, C.TARGET_SHA, out)
            if not (out / 'summary.json').exists():
                (out / 'INCOMPLETE.txt').write_text('Run exited before its summary was saved. Exported responses and proposed changes may be partial.\n')
