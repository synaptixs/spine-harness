"""Native Spine + PKG arm for the matched framework matrix (without OpenSpec)."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from framework_matrix import task_material
from framework_spine_openspec import feature_stages
from project_adapter import ProjectAdapter
from spine_feature import run_project_ticket, verify_spine


def execute(config: dict, task: dict, common: Path, repo: Path, out: Path, baseline: str) -> list[dict]:
    tools = Path(config["tools_dir"])
    verify_spine(tools, config["spine_commit"], config["spine_ref"])
    if not config.get("application_python"):
        raise ValueError("spine-pkg needs an application_python with prepared project dependencies")
    os.environ.update({
        "SPINE_REPO": str(tools),
        "SPINE_CODE_DIR": str(tools),
        "SPINE_REF": config["spine_ref"],
        "WORK_DIR": config["work_dir"],
        "RESULTS_DIR": config["results_dir"],
        "TARGET_DIR": str(common),
        "TARGET_SHA": baseline,
        "CODEX_AUTH": "app",
        "SPINE_BACKEND": "codex",
        "CODEX_LOGIN_HOME": config["login_home"],
        "CODEX_REASONING_EFFORT": config["reasoning_effort"],
        "CODEX_COMPLETION_TIMEOUT_S": str(config["timeout_seconds"]),
        "CODEX_CALLS_DIR": str(out / "codex-calls"),
        "CODEX_OUTPUT_MODE": "envelope",
    })
    sys.path.insert(0, str(tools / "src"))
    from codex_llm import install

    project = ProjectAdapter({
        "repository_url": config.get("repository_url", "local-benchmark-source"),
        "source_repo": config["source_repo"],
        "baseline_commit": baseline,
        "target_dir": str(common),
        "python": config["application_python"],
        "source_paths": config["source_paths"],
        "checks": config["checks"],
        "require_behavior": config.get("require_behavior", False),
        "max_refine": config.get("max_refine", 3),
        "max_judge_revisions": config.get("max_judge_revisions", 2),
        "max_model_calls": config.get("max_model_calls", 24),
    })
    project.verify_target()
    install()
    spec = dict(task.get("spec") or {})
    spec.update(title=task["title"], summary=task_material(task))
    ticket = SimpleNamespace(key=task["id"], spec=spec)
    summary = asyncio.run(run_project_ticket(
        project, ticket, config["model"], out / "feature" / task["id"], out / "codex-calls",
        metadata={"arm": "spine-pkg", "pass": 1, "spine": config["spine_ref"],
                  "spine_commit": config["spine_commit"]},
    ))
    (out / "FEATURE_RESULT.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not summary.get("usage_complete"):
        raise RuntimeError("Spine feature has incomplete response usage")
    patch_file = out / "feature" / task["id"] / "changes.patch"
    if patch_file.is_file() and patch_file.stat().st_size:
        subprocess.run(["git", "-C", str(repo), "apply", "--check", str(patch_file)], check=True)
        subprocess.run(["git", "-C", str(repo), "apply", "--binary", str(patch_file)], check=True)
    return feature_stages(summary)


def main() -> None:
    payload = json.loads(sys.stdin.read())
    out = Path(payload["out"])
    stages = execute(payload["config"], payload["task"], Path(payload["common"]),
                     Path(payload["repo"]), out, payload["baseline"])
    (out / "STAGES.json").write_text(json.dumps(stages, indent=2) + "\n")


if __name__ == "__main__":
    main()
