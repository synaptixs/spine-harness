# Same implementation step with four framework contexts

`context_matrix.py` measures **one implementation and validation step per arm**.
Every arm receives the same issue, committed application baseline, Codex model,
reasoning level, implementation instruction, timeout, and checks. The only
prompt difference is its frozen framework context:

| Arm | Required context provenance |
|---|---|
| `spine-pkg` | Output prepared with Spine + PKG |
| `spine-openspec` | Output prepared with Spine's integrated OpenSpec + PKG |
| `openspec` | Output prepared with standalone OpenSpec |
| `speckit` | Output prepared with SpecKit for the issue and baseline |

This is an **implementation-only** measurement. It does not generate these
contexts or include their preparation cost in the comparison. The existing
`framework_matrix.py` compares full workflows, including distinct generation
stages; do not pool its results with this protocol.

## Freeze and review inputs

Save one task snapshot (Jira JSON, SWE-bench instance, or `id/title/description`
JSON) and four UTF-8 JSON context artifacts. Each artifact has this shape:

```json
{
  "arm": "spine-openspec",
  "task_id": "ISSUE-123",
  "baseline_commit": "<full application commit SHA>",
  "producer": "Spine <pin> + integrated OpenSpec + PKG <pin>",
  "readiness": "approved",
  "text": "<reviewed framework-specific context for implementation>"
}
```

The `producer` and `readiness` fields are declarations, not proof that the
framework ran. Review the source artifacts and pin the actual tool revisions
before marking them approved. For `spine-openspec`, verify that Spine really
used its integrated OpenSpec path; a standalone OpenSpec output is a different
arm. Keep held-out acceptance code out of all four contexts and out of the
model-visible application clone.

Create a config outside the application source checkout. The result and work
directories must also be outside that checkout. The four context keys below
are mandatory. Commands are argv arrays, never shell strings:

```json
{
  "name": "issue-123-attempt-1",
  "source_repo": "/path/to/application",
  "baseline": "<full application commit SHA>",
  "task_file": "/path/to/issue.json",
  "contexts": {
    "speckit": "/path/to/speckit.json",
    "openspec": "/path/to/openspec.json",
    "spine-pkg": "/path/to/spine-pkg.json",
    "spine-openspec": "/path/to/spine-openspec.json"
  },
  "model": "gpt-6-sol",
  "reasoning_effort": "high",
  "login_home": "/path/to/dedicated-codex-home",
  "application_python": "/path/to/application-python",
  "source_paths": ["."],
  "checks": [["{python}", "-m", "pytest", "-q", "tests/test_existing.py"]],
  "acceptance_checks": [["{python}", "/path/to/held-out-acceptance.py"]],
  "known_fix_patch": "/path/to/known-fix.patch",
  "results_dir": "/path/to/results/issue-123-attempt-1",
  "work_dir": "/path/to/work/issue-123-attempt-1"
}
```

## Preflight and run

`prepare` is offline. It verifies all four artifact IDs and baseline pins,
freezes their hashes, prompts, runner files, and Codex CLI version; clones the exact application commit; requires
existing regression checks to pass, requires independent acceptance to fail
on the pre-fix baseline, and checks that a supplied known fix makes both suites
pass. Use a known fix whenever one exists. Check the resulting `PREPARED.json`
and the four frozen context copies. A failure writes `PREFLIGHT_FAILED.json`
and stops before a model call.

```bash
python3 context_matrix.py prepare --config /path/to/context-matrix.json
```

Only after reviewing that evidence and separately authorizing model spending,
start a fresh attempt:

```bash
python3 context_matrix.py run --config /path/to/context-matrix.json --approved
```

`run` uses the existing `model_step` Codex adapter exactly once per arm, in
four independent clones. It refuses to restart an attempt. It preserves patches,
check output, token usage, and API list-price equivalents for completed calls.
`RESULTS.json` and `COMPARISON_REPORT.md` mark incomplete attempts as
non-comparable. Passing configured checks is selected acceptance, not proof of
full issue correctness. Keep the per-attempt `PREPARED.json`, acceptance
evidence, patches, and `RESULTS.json` together when reporting a model run.
