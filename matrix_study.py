#!/usr/bin/env python3
"""Combine closed framework-matrix tasks into a descriptive multi-task study."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from framework_matrix import write, write_html


def passed(checks: list[dict]) -> bool | None:
    return all(row.get("exit") == 0 for row in checks) if checks else None


def exact_sign_p(values: list[float]) -> float | None:
    """Two-sided exact sign test against ratio 1, with ties excluded."""
    higher = sum(value > 1 for value in values)
    lower = sum(value < 1 for value in values)
    n = higher + lower
    if not n:
        return None
    tail = sum(math.comb(n, k) for k in range(min(higher, lower) + 1))
    return min(1.0, 2 * tail / 2**n)


def build(roots: list[Path], output: Path) -> Path:
    roots = [p.resolve() for p in roots]
    if len(roots) < 2 or len(set(roots)) != len(roots):
        raise ValueError("Give at least two distinct closed task result directories")
    if output.exists():
        raise ValueError("Existing study output preserved; choose a fresh directory")
    loaded = []
    for root in roots:
        if not (root / "FINISHED").is_file():
            raise ValueError(f"Task is not closed: {root}")
        data = json.loads((root / "RESULTS.json").read_text())
        experiment = data["experiment"]
        rows = data["runs"]
        expected = {(p, f) for p in range(1, experiment["passes"] + 1) for f in experiment["frameworks"]}
        if {(r["pass"], r["framework"]) for r in rows} != expected or len(rows) != len(expected):
            raise ValueError(f"Missing or duplicate measurements: {root}")
        verification = json.loads((root / "EVIDENCE_VERIFICATION.json").read_text())
        if not verification.get("normalized_task_unchanged") or not verification.get("original_source_unchanged"):
            raise ValueError(f"Source/task integrity was not verified: {root}")
        if not verification.get("functional_comparison_valid") or not verification.get("wall_time_comparison_valid"):
            raise ValueError(f"Invalid or incomplete benchmark protocol: {root}")
        evaluations = (
            json.loads((root / "SWE_EVALUATIONS.json").read_text()) if (root / "SWE_EVALUATIONS.json").exists() else []
        )
        loaded.append((root, experiment, rows, evaluations))
    task_keys = [
        (e.get("repository_url") or e["task"].get("repository") or "unspecified", e["task"]["id"])
        for _, e, _, _ in loaded
    ]
    if len(task_keys) != len(set(task_keys)):
        raise ValueError("A study needs distinct repository/task pairs; duplicate task detected")
    kind = loaded[0][1]["task"]["kind"]
    model = loaded[0][1]["model"]
    reasoning = loaded[0][1]["reasoning_effort"]
    frameworks = loaded[0][1]["frameworks"]
    versions = loaded[0][1].get("framework_versions")
    passes = loaded[0][1]["passes"]
    if any(
        e["task"]["kind"] != kind
        or e["model"] != model
        or e["reasoning_effort"] != reasoning
        or e["frameworks"] != frameworks
        or e.get("framework_versions") != versions
        or e["passes"] != passes
        for _, e, _, _ in loaded
    ):
        raise ValueError("Task type, model/settings, framework versions and passes must match across a study")
    records = []
    for root, exp, rows, evaluations in loaded:
        repository = exp.get("repository_url") or exp["task"].get("repository") or "unspecified"
        official = {x["prediction"]: x for x in evaluations}
        for row in rows:
            pred = f"swebench-predictions/{row['framework']}-pass{row['pass']}.jsonl"
            verdict = official.get(pred, {}).get("resolved")
            records.append(
                {
                    "task_id": exp["task"]["id"],
                    "repository": repository,
                    "baseline_commit": exp.get("baseline_commit"),
                    "task_kind": kind,
                    "pass": row["pass"],
                    "framework": row["framework"],
                    "status": row["status"],
                    "tokens": row["usage"].get("known_tokens") if row["usage"].get("complete") else None,
                    "api_list_price_equivalent_usd": row["usage"].get("api_list_price_equivalent_usd")
                    if row["usage"].get("complete")
                    else None,
                    "workflow_wall_s": row.get("workflow_wall_s"),
                    "total_wall_s": row.get("total_wall_s"),
                    "native_status": row.get("native_status"),
                    "regression_pass": passed(row["regression_checks"]),
                    "acceptance_pass": passed(row["acceptance_checks"]),
                    "selected_checks_passed": row.get("selected_checks_passed"),
                    "official_swebench_resolved": verdict,
                    "protected_inputs_unchanged": row["protected_inputs_unchanged"],
                    "report": str((root / "COMPARISON_REPORT.md").resolve()),
                }
            )
    aggregates = []
    for framework in frameworks:
        selected = [r for r in records if r["framework"] == framework]
        complete = [r for r in selected if r["tokens"] is not None]
        priced = [r for r in selected if r["api_list_price_equivalent_usd"] is not None]
        timed = [r for r in selected if r["workflow_wall_s"] is not None]
        evaluated = [r for r in selected if r["official_swebench_resolved"] is not None]
        acceptance = [r for r in selected if r["acceptance_pass"] is not None]
        checked = [r for r in selected if r["selected_checks_passed"] is not None]
        aggregates.append(
            {
                "framework": framework,
                "measurements": len(selected),
                "usage_complete": len(complete),
                "total_recorded_tokens_complete_rows": sum(r["tokens"] for r in complete),
                "median_tokens_complete_rows": statistics.median(r["tokens"] for r in complete) if complete else None,
                "cost_complete": len(priced),
                "total_api_list_price_equivalent_usd_complete_rows": sum(
                    r["api_list_price_equivalent_usd"] for r in priced
                ),
                "wall_time_observed": len(timed),
                "total_workflow_wall_s_observed": sum(r["workflow_wall_s"] for r in timed),
                "median_workflow_wall_s": statistics.median(r["workflow_wall_s"] for r in timed) if timed else None,
                "workflow_completed": sum(r["status"] == "completed_workflow" for r in selected),
                "acceptance_passed": sum(r["acceptance_pass"] is True for r in acceptance),
                "acceptance_evaluated": len(acceptance),
                "selected_checks_passed": sum(r["selected_checks_passed"] is True for r in checked),
                "selected_checks_evaluated": len(checked),
                "official_resolved": sum(r["official_swebench_resolved"] is True for r in evaluated),
                "official_evaluated": len(evaluated),
            }
        )
    repository_aggregates = []
    for repository in sorted({row["repository"] for row in records}):
        for framework in frameworks:
            selected = [r for r in records if r["repository"] == repository and r["framework"] == framework]
            if not selected:
                continue
            token_rows = [r for r in selected if r["tokens"] is not None]
            priced_rows = [r for r in selected if r["api_list_price_equivalent_usd"] is not None]
            timed_rows = [r for r in selected if r["workflow_wall_s"] is not None]
            repository_aggregates.append(
                {
                    "repository": repository,
                    "framework": framework,
                    "measurements": len(selected),
                    "selected_checks_passed": sum(r["selected_checks_passed"] is True for r in selected),
                    "selected_checks_evaluated": sum(r["selected_checks_passed"] is not None for r in selected),
                    "usage_complete": len(token_rows),
                    "total_tokens_complete_rows": sum(r["tokens"] for r in token_rows),
                    "cost_complete": len(priced_rows),
                    "total_api_list_price_equivalent_usd_complete_rows": sum(
                        r["api_list_price_equivalent_usd"] for r in priced_rows
                    ),
                    "wall_time_observed": len(timed_rows),
                    "median_workflow_wall_s": statistics.median(r["workflow_wall_s"] for r in timed_rows)
                    if timed_rows
                    else None,
                }
            )
    baseline_name = "spine-openspec" if "spine-openspec" in frameworks else frameworks[0]
    ratios = []
    for framework in frameworks:
        if framework == baseline_name:
            continue
        values = []
        task_values = []
        for repository, task_id in task_keys:
            per_task = []
            candidate_rows = [r for r in records if r["repository"] == repository and r["task_id"] == task_id]
            for pass_no in {r["pass"] for r in candidate_rows}:
                current = next(
                    (r for r in candidate_rows if r["pass"] == pass_no and r["framework"] == framework), None
                )
                base = next(
                    (r for r in candidate_rows if r["pass"] == pass_no and r["framework"] == baseline_name), None
                )
                if current and base and current["tokens"] is not None and base["tokens"]:
                    ratio = current["tokens"] / base["tokens"]
                    values.append(ratio)
                    per_task.append(ratio)
            if per_task:
                task_values.append((repository, statistics.median(per_task)))
        repository_values = [
            statistics.median(value for repo, value in task_values if repo == repository)
            for repository in sorted({repo for repo, _ in task_values})
        ]
        ratios.append(
            {
                "framework": framework,
                "reference": baseline_name,
                "paired_n": len(values),
                "independent_task_n": len(task_values),
                "independent_repository_n": len(repository_values),
                "two_sided_exact_repository_sign_p": (
                    exact_sign_p(repository_values) if len(repository_values) >= 2 else None
                ),
                "median_ratio": statistics.median(values) if values else None,
                "minimum_ratio": min(values) if values else None,
                "maximum_ratio": max(values) if values else None,
            }
        )
    result = {
        "task_kind": kind,
        "model": model,
        "reasoning_effort": reasoning,
        "tasks": [task_id for _, task_id in task_keys],
        "repositories": sorted({repository for repository, _ in task_keys}),
        "task_catalog": [{"repository": repository, "task_id": task_id} for repository, task_id in task_keys],
        "frameworks": frameworks,
        "measurements": records,
        "aggregates": aggregates,
        "repository_aggregates": repository_aggregates,
        "paired_token_ratios": ratios,
        "statistical_claim": "Descriptive only; task diversity and repeat variance must be assessed before population inference",
        "cost_label": "API list-price equivalent, not subscription charge",
    }
    output.mkdir(parents=True)
    write(output / "MATRIX_STUDY_RESULTS.json", result)
    lines = [
        "# Multi-task spec-framework benchmark",
        "",
        f"**{len(task_keys)} distinct {kind} tasks in {len(result['repositories'])} "
        f"{'repository' if len(result['repositories']) == 1 else 'repositories'}; "
        f"{len(records)} framework/pass measurements.** Model `{model}` / `{reasoning}`.",
        "Correctness below means **the selected regression and post-run acceptance checks passed with protected inputs intact**. "
        "It is not proof of complete issue correctness; native workflow status is reported separately.",
        "Wall time is elapsed workflow time per arm, excluding its disposable clone and post-run checks. "
        "Dollar figures are API list-price equivalents, not subscription charges. Incomplete usage is unknown, never zero.",
        "",
        "| Framework | Runs | Selected checks passed | Workflow completed | Usage complete | Recorded tokens¹ | Median workflow wall | API-equivalent cost¹ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for a in aggregates:
        tokens = (
            str(a["total_recorded_tokens_complete_rows"])
            if a["usage_complete"] == a["measurements"]
            else f"unknown (known subtotal {a['total_recorded_tokens_complete_rows']})"
        )
        dollars = (
            f"${a['total_api_list_price_equivalent_usd_complete_rows']:.4f}"
            if a["cost_complete"] == a["measurements"]
            else f"unknown (known subtotal ${a['total_api_list_price_equivalent_usd_complete_rows']:.4f})"
        )
        wall = f"{a['median_workflow_wall_s']:.1f} s" if a["median_workflow_wall_s"] is not None else "unknown"
        lines.append(
            f"| {a['framework']} | {a['measurements']} | {a['selected_checks_passed']}/{a['selected_checks_evaluated']} | "
            f"{a['workflow_completed']}/{a['measurements']} | {a['usage_complete']}/{a['measurements']} | "
            f"{tokens} | {wall} ({a['wall_time_observed']}/{a['measurements']}) | "
            f"{dollars} ({a['cost_complete']}/{a['measurements']}) |"
        )
    lines += [
        "",
        "¹ Token and cost totals include only rows with complete recorded usage/pricing; if the denominator is short, "
        "the full-study total is **unknown**. Median wall time uses the observed rows shown in parentheses.",
        "",
        "## By repository",
        "",
        "| Repository | Framework | Runs | Selected checks | Recorded tokens | Median workflow wall | API-equivalent cost |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in repository_aggregates:
        tokens = (
            str(item["total_tokens_complete_rows"]) if item["usage_complete"] == item["measurements"] else "unknown"
        )
        dollars = (
            f"${item['total_api_list_price_equivalent_usd_complete_rows']:.4f}"
            if item["cost_complete"] == item["measurements"]
            else "unknown"
        )
        wall = f"{item['median_workflow_wall_s']:.1f} s" if item["median_workflow_wall_s"] is not None else "unknown"
        lines.append(
            f"| {item['repository']} | {item['framework']} | {item['measurements']} | "
            f"{item['selected_checks_passed']}/{item['selected_checks_evaluated']} | {tokens} | "
            f"{wall} | {dollars} |"
        )
    lines += [
        "",
        "## Paired token ratios",
        "",
    ]
    for item in ratios:
        value = f"{item['median_ratio']:.2f}×" if item["median_ratio"] is not None else "unavailable"
        pvalue = (
            f"{item['two_sided_exact_repository_sign_p']:.4f}"
            if item["two_sided_exact_repository_sign_p"] is not None
            else "not estimable"
        )
        lines.append(
            f"{item['framework']} / {item['reference']}: median **{value}** over {item['paired_n']} matched task-pass pairs "
            f"from {item['independent_task_n']} distinct tasks in {item['independent_repository_n']} repositories. "
            f"Range {item['minimum_ratio']}–{item['maximum_ratio']}. Exact two-sided repository-level sign-test p = {pvalue}."
        )
    if kind == "swebench":
        lines += [
            "",
            "## Official SWE-bench resolution",
            "",
            "| Framework | Officially resolved | Evaluated |",
            "|---|---:|---:|",
        ]
        for a in aggregates:
            lines.append(f"| {a['framework']} | {a['official_resolved']} | {a['official_evaluated']} |")
        lines.append("")
    lines += [
        "",
        "## Per-task evidence",
        "",
        "| Repository | Task | Pass | Framework | Selected checks | Native outcome | Tokens | Workflow wall s | Total wall s | API-equivalent USD | Report |",
        "|---|---|---:|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in records:
        checks = row["selected_checks_passed"]
        check_text = "pass" if checks is True else "fail" if checks is False else "not evaluated"
        tokens = row["tokens"] if row["tokens"] is not None else "unknown"
        workflow_wall = f"{row['workflow_wall_s']:.1f}" if row["workflow_wall_s"] is not None else "unknown"
        total_wall = f"{row['total_wall_s']:.1f}" if row["total_wall_s"] is not None else "unknown"
        dollars = (
            f"${row['api_list_price_equivalent_usd']:.4f}"
            if row["api_list_price_equivalent_usd"] is not None
            else "unknown"
        )
        lines.append(
            f"| {row['repository']} | {row['task_id']} | {row['pass']} | {row['framework']} | {check_text} | "
            f"{row['native_status'] or '—'} | {tokens} | {workflow_wall} | {total_wall} | {dollars} | "
            f"[report]({row['report']}) |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "Unknown usage or pricing makes the full token/cost total unknown; known subtotals are identified as such.",
        "The exact sign test uses repository-level directions after collapsing passes and tasks within each repository. "
        "One repository cannot support a cross-project significance claim. The test says nothing about functional equivalence, "
        "task sampling bias, or PKG causality.",
        "One attempt per task does not estimate run-to-run variance. Related issues, shared prerequisites, human interventions "
        "and framework versions can confound comparisons.",
        "A workflow exit, selected local checks, and an official SWE-bench resolved verdict are different outcomes. "
        "Jira and reference tasks do not receive an official SWE-bench score.",
        "",
    ]
    destination = output / "MATRIX_STUDY_REPORT.md"
    destination.write_text("\n".join(lines))
    write_html(
        output / "MATRIX_STUDY_REPORT.html", "Multi-task spec-framework benchmark", destination.read_text(), aggregates
    )
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.results, args.output))


if __name__ == "__main__":
    main()
