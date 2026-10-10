"""Native Spine OpenSpec adapter for the framework matrix.

The draft is grounded in the same disposable baseline as other arms. Spine then
consumes that OpenSpec change through run_feature; no injected spec is supplied.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from framework_matrix import task_material
from project_adapter import ProjectAdapter
from spine_feature import run_project_ticket, verify_spine


def draft_stage(calls: list[dict]) -> dict:
    usage = {
        key: sum((x.get("usage") or {}).get(key, 0) for x in calls)
        for key in ("input", "cached", "cache_write", "output", "reasoning", "requests")
    }
    return {
        "stage": "openspec_draft",
        "calls": len(calls),
        "usage": usage,
        "known_tokens": usage["input"] + usage["output"],
        "input_tokens": usage["input"],
        "output_tokens": usage["output"],
        "wall_s": round(sum(x.get("wall_s") or 0 for x in calls), 3),
        "api_list_price_equivalent_usd": sum(x["cost_usd"] for x in calls)
        if all(x.get("cost_usd") is not None for x in calls)
        else None,
        "usage_complete": bool(calls) and all(x.get("usage_complete") for x in calls),
    }


def feature_stages(summary: dict) -> list[dict]:
    """Include native intake/spec expansion, which precedes Spine's stage ledger."""
    named = summary.get("stages", {})
    stages = []
    for name, value in named.items():
        stages.append(
            {
                "stage": name,
                "calls": value.get("calls", 0),
                "input_tokens": value.get("prompt_tokens", 0),
                "output_tokens": value.get("completion_tokens", 0),
                "usage": {"cached": value.get("cached_tokens", "not broken out")},
                "known_tokens": value.get("prompt_tokens", 0) + value.get("completion_tokens", 0),
                "wall_s": value.get("wall_s"),
                "api_list_price_equivalent_usd": value.get("cost_usd"),
            }
        )
    input_delta = summary["prompt_tokens"] - sum(stage["input_tokens"] for stage in stages)
    output_delta = summary["completion_tokens"] - sum(stage["output_tokens"] for stage in stages)
    calls_delta = summary["calls"] - sum(stage["calls"] for stage in stages)
    if min(input_delta, output_delta, calls_delta) < 0 or (calls_delta == 0) != (input_delta + output_delta == 0):
        raise RuntimeError("Native Spine stage usage exceeds or conflicts with the full response ledger")
    if calls_delta:
        known_costs = [stage["api_list_price_equivalent_usd"] for stage in stages]
        cost_delta = (
            summary["cost_usd"] - sum(known_costs)
            if summary.get("cost_usd") is not None and all(cost is not None for cost in known_costs)
            else None
        )
        stages.insert(
            0,
            {
                "stage": "feature_intake_spec",
                "calls": calls_delta,
                "input_tokens": input_delta,
                "output_tokens": output_delta,
                "usage": {"cached": "not broken out"},
                "known_tokens": input_delta + output_delta,
                "wall_s": None,
                "api_list_price_equivalent_usd": cost_delta,
                "attribution": "Native full response ledger less the named implementation stages",
            },
        )
    return stages


def record_preapproved_questions(change, config: dict, openspec: Path, out: Path):
    """Apply frozen operator answers or named deferrals through Spine's native gate API."""
    from orchestrator.intake.requirements import AnswerRequest, load_change, record_answers

    def key(text: str) -> str:
        return " ".join(text.split()).casefold()

    answers = config.get("question_answers", {})
    indexed = {key(question): (question, answer) for question, answer in answers.items()}
    policy = config.get("unresolved_question_policy", {"mode": "stop"})
    requests = []
    recorded = []
    matched = set()
    for question in change.intent.open_questions:
        lookup = key(question)
        if lookup in indexed:
            source_question, answer = indexed[lookup]
            requests.append(AnswerRequest(question=question, answer=answer))
            recorded.append({"question": question, "status": "answered", "recorded_answer": answer})
            matched.add(source_question)
        elif policy["mode"] == "defer":
            owner = policy["owner"]
            requests.append(AnswerRequest(question=question, defer_to=owner))
            recorded.append({"question": question, "status": "deferred", "owner": owner})
    if requests:
        record_answers(change, requests, channel="answers-file")
        change = load_change(change.change_id, root=openspec)
    (out / "OPENSPEC_RESOLUTIONS.json").write_text(json.dumps({
        "recorded": recorded,
        "unmatched_recorded_answers": sorted(set(answers) - matched),
        "policy": policy,
        "source": "frozen shared task configuration; model did not answer these questions",
    }, indent=2) + "\n")
    return change


def execute(config: dict, task: dict, common: Path, repo: Path, out: Path, baseline: str) -> list[dict]:
    tools = Path(config.get("tools_dir", ""))
    if not tools.is_dir():
        raise ValueError("spine-openspec requires the pinned Spine tools_dir")
    verify_spine(tools, config["spine_commit"], config["spine_ref"])
    if not config.get("application_python"):
        raise ValueError("spine-openspec needs an application_python with prepared project dependencies")
    context = {
        "SPINE_REPO": str(tools),
        "SPINE_CODE_DIR": str(tools),
        "SPINE_REF": config["spine_ref"],
        "WORK_DIR": str(Path(config["work_dir"])),
        "RESULTS_DIR": str(Path(config["results_dir"])),
        "TARGET_DIR": str(common),
        "TARGET_SHA": baseline,
        "CODEX_AUTH": "app",
        "SPINE_BACKEND": "codex",
        "CODEX_LOGIN_HOME": config["login_home"],
        "CODEX_REASONING_EFFORT": config["reasoning_effort"],
        "CODEX_COMPLETION_TIMEOUT_S": str(config["timeout_seconds"]),
        "CODEX_CALLS_DIR": str(out / "codex-calls"),
        "CODEX_OUTPUT_MODE": "envelope",
        "ORCHESTRATOR_INTAKE_MODEL": config["model"],
        "ORCHESTRATOR_INTAKE_CACHE_DIR": str(out / "draft-cache"),
    }
    os.environ.update(context)
    sys.path.insert(0, str(tools / "src"))
    from orchestrator.cli.build import _run_openspec_draft
    from orchestrator.intake.requirements import check_intent, load_change

    from codex_llm import install

    project = ProjectAdapter(
        {
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
        }
    )
    project.verify_target()
    install()
    source = out / "task-source.md"
    source.write_text(task_material(task) + "\n")
    openspec = out / "openspec"
    (out / "DRAFT_SOURCE.json").write_text(
        json.dumps({"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}, indent=2)
    )

    async def pipeline():
        with patch("orchestrator.core.env.load_local_env", lambda *a, **kw: None):
            await _run_openspec_draft(source.as_uri(), out=str(openspec), refresh=True, overwrite=False, path=str(repo))
        draft_calls = []
        for path in sorted((out / "codex-calls").glob("*/usage.json")):
            draft_calls.append(json.loads(path.read_text()))
        (out / "DRAFT_USAGE.json").write_text(json.dumps(draft_calls, indent=2) + "\n")
        (out / "STAGES.json").write_text(json.dumps([draft_stage(draft_calls)], indent=2) + "\n")
        changes = sorted(p for p in (openspec / "changes").iterdir() if p.is_dir())
        if len(changes) != 1:
            raise RuntimeError(f"Expected exactly one OpenSpec change, got {len(changes)}")
        loaded = load_change(changes[0].name, root=openspec)
        loaded = record_preapproved_questions(loaded, config, openspec, out)
        checked = check_intent(loaded.intent, change_id=loaded.change_id)
        (out / "OPENSPEC_CHECK.json").write_text(json.dumps(checked.to_dict(), indent=2) + "\n")
        if not checked.passes:
            raise RuntimeError("Native OpenSpec clarity check failed; no implementation attempted")
        ticket = SimpleNamespace(key=task["id"], spec={})
        summary = await run_project_ticket(
            project,
            ticket,
            config["model"],
            out / "feature" / task["id"],
            out / "codex-calls",
            metadata={
                "arm": "spine-openspec",
                "pass": 1,
                "spine": config["spine_ref"],
                "spine_commit": config["spine_commit"],
            },
            source_uri=f"openspec://{loaded.change_id}",
            openspec_root=openspec,
        )
        (out / "FEATURE_RESULT.json").write_text(json.dumps(summary, indent=2) + "\n")
        if not summary.get("usage_complete"):
            raise RuntimeError("Spine feature has incomplete response usage")
        return summary

    summary = asyncio.run(pipeline())
    patch_file = out / "feature" / task["id"] / "changes.patch"
    if patch_file.is_file() and patch_file.stat().st_size:
        subprocess.run(["git", "-C", str(repo), "apply", "--check", str(patch_file)], check=True)
        subprocess.run(["git", "-C", str(repo), "apply", "--binary", str(patch_file)], check=True)
    draft_calls = json.loads((out / "DRAFT_USAGE.json").read_text())
    stages = [draft_stage(draft_calls), *feature_stages(summary)]
    return stages


def main() -> None:
    """Read a single local worker payload; never place task text on argv."""
    payload = json.loads(sys.stdin.read())
    out = Path(payload["out"])
    stages = execute(
        payload["config"],
        payload["task"],
        Path(payload["common"]),
        Path(payload["repo"]),
        out,
        payload["baseline"],
    )
    (out / "STAGES.json").write_text(json.dumps(stages, indent=2) + "\n")


if __name__ == "__main__":
    main()
