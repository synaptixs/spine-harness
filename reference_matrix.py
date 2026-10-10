#!/usr/bin/env python3
"""Prepare and run the selected reference scenarios across four matched frameworks.

This is the default 33-scenario matrix. The historical two-arm run_comparison.py
remains available for reproduction of earlier studies. No model calls occur in
dry-run or prepare; run requires explicit --approved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import harness_config as C
from framework_matrix import load, prepare, run, write
from matrix_study import build as build_study

FRAMEWORKS = ("speckit", "openspec", "spine-openspec", "spine-pkg")
ROOT = Path(__file__).resolve().parent


def catalog() -> dict:
    command = [
        "uv",
        "run",
        "--frozen",
        "--project",
        str(C.SPINE_CODE_DIR),
        "python",
        str(ROOT / "scenarios.py"),
        "export",
        "--tree",
        "target",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    data = json.loads(result.stdout)
    if len(data["scenarios"]) != len(C.TICKETS):
        raise RuntimeError("Scenario export does not match the selected tickets")
    return data


def paths() -> tuple[Path, Path]:
    return C.RESULTS_DIR / "reference-matrix", C.WORK_DIR / "reference-matrix"


def task_text(scenario: dict) -> str:
    spec = scenario["spec"]
    criteria = "\n".join(f"- {line}" for line in spec["acceptance_criteria"])
    return f"{spec['summary']}\n\nTechnical notes: {spec['technical_notes']}\n\nAcceptance criteria:\n{criteria}"


def config_for(scenario: dict, root: Path, work: Path, *, model: str, passes: int, spine_commit: str) -> dict:
    key = scenario["key"]
    inputs = root / "inputs" / key
    return {
        "name": f"reference-{key.lower()}",
        "source_repo": str(C.TARGET_DIR.resolve()),
        "repository_url": "https://github.com/synaptixs/spine",
        "baseline": subprocess.check_output(["git", "-C", str(C.TARGET_DIR), "rev-parse", "HEAD"], text=True).strip(),
        "task_file": str(inputs / "task.json"),
        "frameworks": list(FRAMEWORKS),
        "model": model,
        "reasoning_effort": C.CODEX_REASONING_EFFORT,
        "passes": passes,
        "approve_checklist": True,
        "login_home": str(C.CODEX_LOGIN_HOME.resolve()),
        "tools_dir": str(C.SPINE_CODE_DIR.resolve()),
        "spine_commit": spine_commit,
        "spine_ref": C.SPINE_REF,
        "application_python": str((C.TARGET_DIR / ".venv/bin/python").absolute()),
        "source_paths": [".", "src"],
        "checks": [["{python}", "scripts/state-numbers.py", "--check"]],
        "acceptance_checks": [
            ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider", str(inputs / name)]
            for name in sorted(scenario["held_out_tests"])
        ],
        "results_dir": str(root / "runs" / key),
        "work_dir": str(work / key),
        "task_context": {
            "problem": "The reference repository lacks the behavior described in this synthetic benchmark task.",
            "users": "Developers and maintainers calling the specified Python API.",
            "outcome": "Implement the stated acceptance criteria while preserving existing repository behavior.",
        },
    }


def manifest(root: Path) -> dict:
    path = root / "MATRIX_PLAN.json"
    if not path.is_file():
        raise ValueError(f"Prepare the reference matrix first: {path}")
    data = json.loads(path.read_text())
    for item in data["scenarios"]:
        config = root / "configs" / f"{item['key']}.json"
        if hashlib.sha256(config.read_bytes()).hexdigest() != item["config_sha256"]:
            raise ValueError(f"Frozen config changed: {config}")
    return data


def prepare_all(model: str, passes: int) -> Path:
    root, work = paths()
    if root.exists() or work.exists():
        raise ValueError("Reference matrix already exists; choose fresh WORK_DIR and RESULTS_DIR")
    data = catalog()
    spine_commit = subprocess.check_output(["git", "-C", str(C.SPINE_CODE_DIR), "rev-parse", "HEAD"], text=True).strip()
    root.mkdir(parents=True)
    items = []
    for scenario in data["scenarios"]:
        key = scenario["key"]
        inputs = root / "inputs" / key
        inputs.mkdir(parents=True)
        write(
            inputs / "task.json",
            {
                "id": key,
                "kind": "reference",
                "title": scenario["spec"]["title"],
                "description": task_text(scenario),
                "spec": scenario["spec"],
            },
        )
        for name, body in scenario["held_out_tests"].items():
            (inputs / name).write_text(body)
        config = root / "configs" / f"{key}.json"
        write(config, config_for(scenario, root, work, model=model, passes=passes, spine_commit=spine_commit))
        items.append(
            {
                "key": key,
                "config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
                "held_out_sha256": {
                    name: hashlib.sha256(body.encode()).hexdigest()
                    for name, body in sorted(scenario["held_out_tests"].items())
                },
            }
        )
    write(
        root / "MATRIX_PLAN.json",
        {
            "schema_version": 1,
            "scenario_fingerprint": data["scenario_fingerprint"],
            "stock_held_out_suite": data["stock_held_out_suite"],
            "custom_catalog": data["custom_catalog"],
            "frameworks": FRAMEWORKS,
            "model": model,
            "passes": passes,
            "spine_ref": C.SPINE_REF,
            "spine_commit": spine_commit,
            "scenarios": items,
            "expected_ticket_arm_measurements": len(items) * passes * len(FRAMEWORKS),
        },
    )
    for item in items:
        config = load(root / "configs" / f"{item['key']}.json")
        prepare(config)
    return root


def run_all(approved: bool) -> Path:
    if not approved:
        raise ValueError("Model execution requires --approved")
    root, _ = paths()
    data = manifest(root)
    for item in data["scenarios"]:
        result = root / "runs" / item["key"]
        if (result / "FINISHED").exists():
            continue
        if (result / "STARTED").exists():
            raise RuntimeError(f"Interrupted attempt requires review, not replay: {result}")
        run(load(root / "configs" / f"{item['key']}.json"), True)
    return report_all()


def report_all() -> Path:
    root, _ = paths()
    data = manifest(root)
    runs = [root / "runs" / item["key"] for item in data["scenarios"]]
    if not all((result / "FINISHED").exists() for result in runs):
        raise ValueError("All selected scenario runs must close before the study report")
    if len(runs) == 1:
        return runs[0] / "COMPARISON_REPORT.md"
    destination = root / "study"
    if destination.exists():
        raise ValueError(f"Study report already exists: {destination}")
    return build_study(runs, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("dry-run", "prepare", "run", "report"))
    parser.add_argument("--model", default=os.environ.get("MODEL", "gpt-6-sol"))
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    if args.passes < 1:
        parser.error("--passes must be positive")
    if args.action == "dry-run":
        data = catalog()
        print(
            f"{len(data['scenarios'])} scenarios × {len(FRAMEWORKS)} frameworks × {args.passes} pass(es) "
            f"= {len(data['scenarios']) * len(FRAMEWORKS) * args.passes} ticket-arm measurements"
        )
        print("Frameworks: " + ", ".join(FRAMEWORKS))
        for item in data["scenarios"]:
            print(f"{item['key']}: {', '.join(FRAMEWORKS)}")
    elif args.action == "prepare":
        print(prepare_all(args.model, args.passes))
    elif args.action == "run":
        print(run_all(args.approved))
    else:
        print(report_all())


if __name__ == "__main__":
    main()
