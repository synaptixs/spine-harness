"""Produce one frozen context using Spine's integrated OpenSpec draft and PKG.

The native Spine draft is the only model-spending step here. This producer
does not run Spine's implementation pipeline or edit the application clone.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    if not args.approved:
        raise ValueError("Native Spine draft requires explicit model authorization")

    from context_matrix import load_config
    from framework_matrix import task_from_file, task_material

    config = load_config(args.config)
    repo, out = args.repo.resolve(), args.out.resolve()
    if (out.parent / "STOPPED.json").exists():
        raise ValueError("Context attempt is stopped")
    if out.exists():
        raise ValueError("Preserving existing native Spine draft attempt")
    if subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip() != config["baseline"]:
        raise ValueError("Application clone is not at the frozen baseline")
    if subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True).strip():
        raise ValueError("Application clone is not clean")

    tools = Path(config["spine_tools"])
    if subprocess.check_output(["git", "-C", str(tools), "rev-parse", "HEAD"], text=True).strip() != config["spine_commit"]:
        raise ValueError("Spine tools commit differs from pin")
    out.mkdir(parents=True)
    os.environ.update({
        "SPINE_REPO": str(tools),
        "SPINE_CODE_DIR": str(tools),
        "WORK_DIR": str(out / "runtime"),
        "RESULTS_DIR": str(out),
        "TARGET_DIR": str(repo),
        "TARGET_SHA": config["baseline"],
        "CODEX_AUTH": "app",
        "SPINE_BACKEND": "codex",
        "CODEX_LOGIN_HOME": config["login_home"],
        "CODEX_REASONING_EFFORT": config["reasoning_effort"],
        "CODEX_COMPLETION_TIMEOUT_S": str(config["timeout_seconds"]),
        "CODEX_CALLS_DIR": str(out / "codex-calls"),
        "CODEX_OUTPUT_MODE": "envelope",
        "ORCHESTRATOR_INTAKE_MODEL": config["model"],
        "ORCHESTRATOR_INTAKE_CACHE_DIR": str(out / "intake-cache"),
    })
    sys.path.insert(0, str(tools / "src"))
    from orchestrator.cli.build import _run_openspec_draft
    from orchestrator.intake.requirements import check_intent, load_change

    from codex_llm import install

    install()
    task = task_from_file(Path(config["task_file"]))
    source = out / "task-source.md"
    source.write_text(task_material(task) + "\n")
    openspec = out / "openspec"
    with patch("orchestrator.core.env.load_local_env", lambda *a, **kw: None), patch(
        "orchestrator.pkg.persistence.default_cache_dir", lambda: out / "pkg-cache"
    ):
        asyncio.run(_run_openspec_draft(source.as_uri(), out=str(openspec), refresh=True,
                                        overwrite=False, path=str(repo)))

    changes = sorted(path for path in (openspec / "changes").iterdir() if path.is_dir())
    if len(changes) != 1:
        raise ValueError(f"Native Spine draft produced {len(changes)} changes; expected one")
    change = load_change(changes[0].name, root=openspec)
    check = check_intent(change.intent, change_id=change.change_id)
    (out / "OPENSPEC_CHECK.json").write_text(json.dumps(check.to_dict(), indent=2) + "\n")
    if not check.passes:
        raise ValueError("Native Spine OpenSpec clarity gate failed; inspect the preserved draft")
    files = sorted(changes[0].rglob("*.md"))
    if not files or not (changes[0] / "proposal.md").is_file():
        raise ValueError("Native draft lacks proposal or Markdown specs")
    sections = []
    hashes = {}
    for path in files:
        rel = path.relative_to(openspec).as_posix()
        hashes[rel] = sha(path)
        sections.append(f"## {rel}\n\n{path.read_text()}")
    content = "# Spine + integrated OpenSpec + PKG context\n\n" + "\n\n".join(sections)
    if len(content.encode()) > 65536:
        raise ValueError("Native Spine context exceeds 64 KiB")
    calls = [json.loads(path.read_text()) for path in sorted((out / "codex-calls").glob("*/usage.json"))]
    if not calls or not all(call.get("usage_complete") and call.get("model") == config["model"] for call in calls):
        raise ValueError("Native Spine draft lacks complete pinned-model usage")
    if subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain"], text=True).strip():
        raise ValueError("Native draft changed the application clone")
    artifact = Path(config["contexts"]["spine-openspec"])
    if artifact.exists():
        raise ValueError("Refusing to overwrite context artifact")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({
        "arm": "spine-openspec", "task_id": task["id"],
        "baseline_commit": config["baseline"],
        "producer": f"Spine {config['spine_version']} ({config['spine_commit']}) integrated OpenSpec draft + PKG",
        "readiness": "review_pending", "text": content,
        "evidence": {
            "source_sha256": sha(source), "source_files_sha256": hashes,
            "check_sha256": sha(out / "OPENSPEC_CHECK.json"),
            "model_calls": len(calls),
            "model_input_tokens": sum(call["usage"]["input"] for call in calls),
            "model_output_tokens": sum(call["usage"]["output"] for call in calls),
            "api_list_price_equivalent_usd": sum(call["cost_usd"] for call in calls),
            "producer_script_sha256": sha(Path(__file__)),
        },
    }, indent=2, sort_keys=True) + "\n")
    print(artifact)


if __name__ == "__main__":
    main()
