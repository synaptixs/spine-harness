"""Every path and version the harness uses, read from the environment (see env.example).

Nothing here is specific to one machine. Import this first: it also puts the right trees on
sys.path, so `codegen_benchmark` (tickets, graders) comes from the TARGET tree for the spec-kit
arm and from the SPINE_CODE tree for the Spine + PKG arm, exactly as the published runs did.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None or v == "":
        raise SystemExit(f"{name} is not set — copy env.example to .env, fill it in, and `source .env`")
    return v


def _uv_dir(sub: str) -> str:
    try:
        return subprocess.run(["uv", sub, "dir"] if sub == "cache" else ["uv", "python", "dir"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


HERE = Path(__file__).resolve().parent
SPINE_REPO = Path(_env("SPINE_REPO")).expanduser().resolve()          # a checkout of synaptixs/spine
WORK_DIR = Path(_env("WORK_DIR", "/tmp/speckit-bench")).expanduser()    # throwaway worktrees; NOT under $HOME
RESULTS_DIR = Path(_env("RESULTS_DIR", str(HERE / "results"))).expanduser()
TARGET_SHA = _env("TARGET_SHA", "bd16dbb7")                            # the commit both tools change
TARGET_DIR = Path(_env("TARGET_DIR", str(WORK_DIR / "target"))).expanduser()
SPINE_REF = _env("SPINE_REF", "v3.52.0")                               # the Spine version measured
SPINE_CODE_DIR = Path(_env("SPINE_CODE_DIR", str(WORK_DIR / "spine-code"))).expanduser()
PROJECT_CONFIG = Path(os.environ['PROJECT_CONFIG']).expanduser().resolve() if os.environ.get('PROJECT_CONFIG') else None
PROJECT = None
if PROJECT_CONFIG:
    from project_adapter import ProjectAdapter
    PROJECT = ProjectAdapter.read(PROJECT_CONFIG)
    TARGET_DIR = Path(PROJECT.config['target_dir']).resolve()
    TARGET_SHA = PROJECT.config['baseline_commit']

SPECKIT = "git+https://github.com/github/spec-kit.git@" + _env("SPECKIT_REF", "v1.0.11")
UV_CACHE = os.environ.get("UV_CACHE_DIR") or _uv_dir("cache")
UV_PYTHON = os.environ.get("UV_PYTHON_INSTALL_DIR") or _uv_dir("python")
BUNDLED_CATALOG = HERE / "catalog" / "expanded.json"
DEFAULT_TICKETS = ["NEW-SEVSUMMARY-1", "NEW-LEDGERMD-1", "NEW-DRIFTMD-1"] + [
    row["key"] for row in json.loads(BUNDLED_CATALOG.read_text())["scenarios"]
]
TICKETS = [k.strip() for k in _env("TICKETS", ",".join(DEFAULT_TICKETS)).split(",")]
SCENARIO_FILE = Path(os.environ['SCENARIO_FILE']).expanduser().resolve() if os.environ.get('SCENARIO_FILE') else BUNDLED_CATALOG
if SCENARIO_FILE and any(SCENARIO_FILE.is_relative_to(p.resolve()) for p in (WORK_DIR, SPINE_REPO)):
    raise SystemExit('Keep SCENARIO_FILE and held-out tests outside WORK_DIR and SPINE_REPO')
#: How spec-kit's Codex runs sign in. "api-key" (default, as published): OPENAI_API_KEY, logged in to a
#: throwaway CODEX_HOME per run. "app": a ChatGPT sign-in (the Codex app's subscription), made once in
#: CODEX_LOGIN_HOME with `CODEX_HOME=<it> codex login`; your own ~/.codex is never read or changed.
#: SPINE_BACKEND=codex routes Spine through the same isolated ChatGPT sign-in.
CODEX_AUTH = _env("CODEX_AUTH", "api-key")
if CODEX_AUTH not in ("api-key", "app"):
    raise SystemExit(f"CODEX_AUTH must be 'api-key' or 'app', not {CODEX_AUTH!r}")
CODEX_LOGIN_HOME = Path(_env("CODEX_LOGIN_HOME", str(WORK_DIR / "codex-app-login"))).expanduser()
SPINE_BACKEND = _env("SPINE_BACKEND", "api")
if SPINE_BACKEND not in ("api", "codex"):
    raise SystemExit("SPINE_BACKEND must be api or codex")
CODEX_REASONING_EFFORT = _env("CODEX_REASONING_EFFORT", "high")
STEP_TIMEOUT_S = 45 * 60
# Optional override for Spine's completion client, whose upstream default is 300s.
CODEX_COMPLETION_TIMEOUT_S = (float(os.environ['CODEX_COMPLETION_TIMEOUT_S'])
                              if os.environ.get('CODEX_COMPLETION_TIMEOUT_S') else None)
if CODEX_COMPLETION_TIMEOUT_S is not None and not 0 < CODEX_COMPLETION_TIMEOUT_S < float('inf'):
    raise SystemExit('CODEX_COMPLETION_TIMEOUT_S must be a positive finite number')
QUOTA_MARKERS = ("quota exceeded", "insufficient_quota", "check your plan and billing") + (
    ("usage limit",) if CODEX_AUTH == "app" else ())  # a ChatGPT plan reports its limits in its own words
STOP = RESULTS_DIR / "QUOTA_STOP"  # written on the first quota error; every job checks it
CLARIFY_ANSWER = (
    "No further detail is available. Use reasonable defaults for every open question, "
    "record them in the spec, and finish the clarification."
)


def codex_env() -> dict[str, str]:
    env = dict(os.environ, CODEX_HOME=str(CODEX_LOGIN_HOME), UV_CACHE_DIR=UV_CACHE)
    if CODEX_AUTH == "app":
        for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN"):
            env.pop(key, None)
    if PROJECT:
        keep = {'PATH','HOME','LANG','LC_ALL','TMPDIR','SYSTEMROOT','CODEX_HOME','UV_CACHE_DIR',
                'UV_PYTHON_INSTALL_DIR','UV_PYTHON','CODEX_OUTPUT_MODE'}
        env = {k:v for k,v in env.items() if k in keep}
    return env


def use_tree(tree: Path) -> None:
    """Import `codegen_benchmark` and `orchestrator` from `tree` (a Spine checkout)."""
    if PROJECT:
        tree = SPINE_CODE_DIR
    if not (tree / "scripts/codegen_benchmark.py").exists():
        raise SystemExit(f"{tree} is not a Spine tree — run ./setup.sh first")
    sys.path.insert(0, str(tree / "scripts"))
    sys.path.insert(0, str(tree / "src"))


def ticket_text(t, heading: bool = False) -> str:  # type: ignore[no-untyped-def]
    """The ticket exactly as both tools received it."""
    s = t.spec
    crit = "\n".join(f"- {c}" for c in s["acceptance_criteria"])
    title = f"# {s['title']}" if heading else s["title"]
    return f"{title}\n\n{s['summary']}\n\nTechnical notes: {s['technical_notes']}\n\nAcceptance criteria:\n{crit}" + (
        "\n" if heading else "")


def configure_tickets(cb):
    import json

    from scenario_catalog import configure, fingerprint
    metadata = configure(cb, TICKETS, SCENARIO_FILE, TARGET_DIR)
    if metadata and metadata.get('evaluation_mode')=='tokens-only' and not PROJECT:
        raise SystemExit('Token-only scenarios require PROJECT_CONFIG')
    experiment = RESULTS_DIR / 'EXPERIMENT.json'
    if experiment.exists():
        saved = json.loads(experiment.read_text())
        if PROJECT and saved.get('project') != PROJECT.config:
            raise SystemExit('Project configuration changed since EXPERIMENT.json')
        if saved['scenario_fingerprint'] != fingerprint(cb.TICKETS) or saved.get('custom_catalog') != metadata:
            raise SystemExit('Scenario catalog/judge changed since EXPERIMENT.json; refusing model execution')
    return metadata


def require_project_execution():
    if not PROJECT:
        return
    if os.environ.get('BENCHMARK_EXECUTE') != '1':
        raise SystemExit('Project execution disabled. Explicitly set BENCHMARK_EXECUTE=1 only when ready to run models.')
    import hashlib
    PROJECT.verify_target()
    PROJECT.verify_execution_sandbox()
    if not PROJECT.config.get("baseline_reviewed"):
        raise SystemExit("Review issue suitability at the pinned baseline and set baseline_reviewed in PROJECT.json")
    review = SCENARIO_FILE.parent / 'REVIEW.json'
    data = json.loads(review.read_text()) if review.is_file() else {}
    if not data.get('reviewed') or data.get('catalog_sha256') != hashlib.sha256(SCENARIO_FILE.read_bytes()).hexdigest():
        raise SystemExit('Review the frozen Jira catalog and baseline, then update its REVIEW.json before execution.')
