"""Generate and freeze SpecKit or standalone OpenSpec context before implementation.

Each `stage` call spends model tokens and is one-shot. `pack` is offline and
refuses incomplete specification work. Spine's integrated OpenSpec draft is a
separate native producer, not the standalone OpenSpec CLI path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from .context_matrix import load_config
from .framework_matrix import model_step, task_from_file, task_prompt, write

STAGES = {
    "speckit": ("specify", "clarify", "plan", "tasks", "analyze"),
    "openspec": ("propose",),
}
PROMPTS = {
    "specify": "$speckit-specify Create a specification for this issue. Do not implement.\n\n",
    "clarify": "$speckit-clarify Resolve ambiguity from the issue text only. Do not invent an owner decision. Do not implement.",
    "plan": "$speckit-plan Produce an implementation plan. Do not implement.",
    "tasks": "$speckit-tasks Produce actionable implementation tasks. Do not implement.",
    "analyze": "$speckit-analyze Check the specification, plan, and tasks. Do not implement.",
    "propose": "$openspec-propose Create one change with proposal, specs, design, and tasks for this issue. "
               "Do not implement.\n\n",
}
ALLOWED_PREFIXES = (".agents/", ".codex/", ".specify/", "specs/", "openspec/")


def changed_paths(repo: Path) -> list[str]:
    tracked = subprocess.check_output(
        ["git", "-C", str(repo), "diff", "--name-only", "HEAD", "--"], text=True
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"], text=True
    ).splitlines()
    return sorted(set(tracked + untracked))


def verify_spec_only(repo: Path) -> None:
    outside = [path for path in changed_paths(repo) if not path.startswith(ALLOWED_PREFIXES)]
    if outside:
        raise ValueError("Context generation changed application files: " + ", ".join(outside[:10]))


def generate_stage(config: dict, arm: str, stage: str, repo: Path, out: Path) -> dict:
    order = STAGES[arm]
    if stage not in order:
        raise ValueError(f"Unexpected stage {stage} for {arm}")
    if (out.parent / "STOPPED.json").exists():
        raise ValueError("Context attempt is stopped; create a fresh matched attempt")
    if subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip() != config["baseline"]:
        raise ValueError("Context clone is not at the shared baseline")
    if not (repo / (".specify" if arm == "speckit" else "openspec/config.yaml")).exists():
        raise ValueError("Framework is not initialized in the disposable clone")
    out.mkdir(parents=True, exist_ok=True)
    ledger = out / "STAGES.json"
    state = json.loads(ledger.read_text()) if ledger.is_file() else {"arm": arm, "stages": [], "thread": None}
    if state["arm"] != arm or [row["stage"] for row in state["stages"]] != list(order[:order.index(stage)]):
        raise ValueError("Stages must run once and in order; preserve partial attempts")
    if arm == "speckit" and stage == "plan":
        review = out / "SCOPE_REVIEW.json"
        if not review.is_file():
            raise ValueError("SpecKit clarification requires a recorded scope review before planning")
        decision = json.loads(review.read_text())
        if decision.get("task_sha256") != hashlib.sha256(Path(config["task_file"]).read_bytes()).hexdigest() or \
                decision.get("scope_resolved") is not True:
            raise ValueError("Scope review does not approve the frozen task snapshot")
    marker = out / (stage + ".STARTED")
    if marker.exists():
        raise ValueError("Stage already started; never silently retry")
    verify_spec_only(repo)
    task = task_from_file(Path(config["task_file"]))
    instruction = PROMPTS[stage]
    if stage in ("specify", "propose"):
        instruction += task_prompt(task)
    marker.write_text("started\n")
    try:
        thread, result = model_step(config, repo, out, stage, instruction, state["thread"])
        verify_spec_only(repo)
        state["thread"] = thread
        state["stages"].append(result)
        write(ledger, state)
        return result
    except Exception as exc:
        write(out / (stage + ".FAILED.json"), {"error": f"{type(exc).__name__}: {exc}"})
        raise


def specification_files(arm: str, repo: Path) -> list[Path]:
    if arm == "speckit":
        files = sorted((repo / "specs").rglob("*.md"))
        if not any(path.name == "spec.md" for path in files):
            raise ValueError("SpecKit did not produce a spec.md")
    else:
        changes = sorted(path for path in (repo / "openspec/changes").iterdir()
                         if path.is_dir() and path.name != "archive")
        if len(changes) != 1 or not (changes[0] / "proposal.md").is_file():
            raise ValueError("OpenSpec must produce exactly one proposal change")
        files = sorted(changes[0].rglob("*.md"))
    if not files:
        raise ValueError("No specification files were produced")
    return files


def pack(config: dict, arm: str, repo: Path, out: Path, artifact: Path) -> dict:
    if (out.parent / "STOPPED.json").exists():
        raise ValueError("Context attempt is stopped; it cannot be packed")
    state = json.loads((out / "STAGES.json").read_text())
    if [row["stage"] for row in state["stages"]] != list(STAGES[arm]):
        raise ValueError("Specification stages are incomplete")
    verify_spec_only(repo)
    files = specification_files(arm, repo)
    if arm == "openspec":
        change = files[0].relative_to(repo).parts[2]
        checked = subprocess.run([config["openspec_bin"], "validate", change, "--strict", "--no-interactive"],
                                 cwd=repo, capture_output=True, text=True, timeout=60)
        (out / "validate.log").write_text(checked.stdout + checked.stderr)
        if checked.returncode:
            raise ValueError("Standalone OpenSpec validation failed")
    sections = []
    hashes = {}
    for path in files:
        rel = path.relative_to(repo).as_posix()
        body = path.read_text()
        hashes[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        sections.append(f"## {rel}\n\n{body}")
    content = "# " + ("SpecKit" if arm == "speckit" else "Standalone OpenSpec") + " context\n\n" + "\n\n".join(sections)
    if len(content.encode()) > 65536:
        raise ValueError("Specification context exceeds 64 KiB; review scope instead of clipping")
    tool = (config["speckit_ref"] + " (" + config["speckit_commit"] + ")"
            if arm == "speckit" else "OpenSpec " + config["openspec_version"])
    data = {
        "arm": arm, "task_id": task_from_file(Path(config["task_file"]))["id"],
        "baseline_commit": config["baseline"], "producer": tool,
        "readiness": "review_pending", "text": content,
        "evidence": {"source_sha256": hashes, "stage_ledger_sha256": hashlib.sha256((out / "STAGES.json").read_bytes()).hexdigest(),
                     "producer_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
    }
    if artifact.exists():
        raise ValueError("Refusing to overwrite an existing context artifact")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    write(artifact, data)
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("stage", "pack"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--arm", choices=tuple(STAGES), required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--stage", choices=tuple(PROMPTS))
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.action == "stage":
        if not args.approved or not args.stage:
            raise ValueError("A named model stage requires --approved")
        print(generate_stage(config, args.arm, args.stage, args.repo, args.out))
    else:
        if args.stage:
            raise ValueError("pack does not take --stage")
        print(pack(config, args.arm, args.repo, args.out, Path(config["contexts"][args.arm]))["evidence"])


if __name__ == "__main__":
    main()
