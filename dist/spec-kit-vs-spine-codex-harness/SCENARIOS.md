# Adding and validating scenarios

This release supports additional **Python create/edit tasks on the pinned Spine repository**. It does not turn a different SPINE_REPO into a supported target automatically. Setup, package discovery, static checks, and the documented-count gate are Spine-specific.

For Jira issues in a different application repository, see **QUICKSTART.md, section 5** for the issue mapping, held-out example, and adapter requirements. The default benchmark remains a reference-repository run; custom JSON alone does not change the target.

## Scenario file contract

By default `SCENARIO_FILE` uses `catalog/expanded.json`, adding 30 tasks; TICKETS selects the original three plus those 30. See [catalog/INDEX.md](catalog/INDEX.md). To use your own extension, set `SCENARIO_FILE` to its absolute path outside WORK_DIR and SPINE_REPO, and set TICKETS to matching IDs. An explicit catalog replaces the bundled extension. The file extends the built-in catalog; it does not replace or rename existing IDs. TICKETS selects the IDs for the experiment. IDs not present in either catalog fail validation before any model call.

```json
{
  "schema_version": 1,
  "scenarios": [
    {
      "key": "TEAM-EDIT-EXAMPLE-1",
      "kind": "edit",
      "must_edit": ["src/orchestrator/pkg/stats.py"],
      "spec": {
        "title": "A concise task title",
        "summary": "Describe the required behavior and its boundaries.",
        "technical_notes": "Name the existing types, constraints, and integration requirements.",
        "acceptance_criteria": ["A concrete observable outcome", "A boundary or error case"]
      },
      "held_out_tests": ["heldout/test_example.py"]
    }
  ]
}
```

This contract illustration needs a real held-out file and a complete task definition before it can run. For runnable examples, copy `examples/` instead.

| Field | Rule |
|---|---|
| `schema_version` | Exactly `1`. |
| `scenarios` | Nonempty list; duplicate IDs are rejected. |
| `key` | Uppercase letters/digits separated by hyphens, e.g. `TEAM-EDIT-CACHE-1`; no built-in collision. |
| `kind` | `create` or `edit`. |
| `spec` | Exactly `title`, `summary`, `technical_notes`, and a nonempty list of `acceptance_criteria`. |
| `must_edit` | Required, nonempty, repo-relative existing file paths for `edit`; absent or empty for `create`. |
| `held_out_tests` | Nonempty list of relative paths beneath the catalog directory. Each basename must be unique within the scenario and match `test_*.py`. |

Unknown fields, traversal paths, missing files, syntax errors, and missing edit targets are rejected. Hashes cover both catalog bytes and test bytes. The same loaded Ticket objects and judge contents feed spec-kit, Spine, and intake; tests are only passed to grading, not to model ticket text. Intake is still measured separately from codegen.

Keep held-out files outside generated worktrees and out of the target repository's graph. This is procedural test separation, not a security boundary against a model that can read host files. Trusted operators author and review the tests; they are executable Python code.

## Authoring useful tests

1. Start from a requirement that is genuinely different from the existing tasks. Renaming the histogram function ten times does not add meaningful problem diversity.
2. State behavior clearly enough that both workflows receive the same contract. For an edit, name the target in the task and `must_edit`. For a create task, choose whether finding the module location is part of the task, and make the tests consistent with that choice.
3. Write independent pytest assertions for normal, empty, boundary, error, and preservation behavior as appropriate. Use the target's real types rather than stand-ins that accidentally impose a different API.
4. Confirm the judge fails on the untouched target when the feature is absent, passes a known-correct reference implementation, and rejects a plausible wrong implementation. Keep that reference solution out of model context and out of the target checkout used by the experiment.
5. Run syntax/catalog validation and a dry run, then one model pilot. Review the generated code, judge output, and scoring before launching repeats.

The included range and histogram judges were checked against missing, deliberately wrong, and known-correct implementations offline. They are examples of the extension mechanism, not a claim that these two tasks provide broad benchmark coverage.

## Grading behavior

Both workflows receive held-out tests and retain their existing workflow checks. Spec-kit's changed-file detection now includes tracked edits (staged or unstaged) and newly created Python source/test files, so edit-only solutions are graded rather than mistaken for no implementation. Deleted Python files do not count as an implementation; deletion-only or non-Python tasks are outside this adapter's supported scope.

The inherited `fit` grader has two policies:

- **Edit:** every `must_edit` file must change, no parallel source module may be introduced, and unrelated tracked-file edits fail the fit rule. Tests are allowed. Use a create task or a new explicit grader design for changes that intentionally combine multiple new modules and tracked edits; do not relabel such work to evade the rule.
- **Create:** a new module must be inside a detected package, reuse repository code, and leave tracked files unchanged. This is suitable for integration/grounding tasks that use existing models; a standalone utility with no repository imports would fail this fit rule even if its behavior is correct.

The repository gate is specifically `scripts/state-numbers.py --check`. Fixing documented counts can conflict with the inherited strict fit rule. Report both outcomes and inspect edits; a fit failure is not automatically harmful behavior. Own-test and held-out results remain separate.

## Scope and reproducibility

You can mix stock and custom IDs in TICKETS and choose any positive repeat count. All selected tasks run against one target commit per experiment. The runner records `EXPERIMENT.json` and rejects differences between the pinned target and Spine task definitions before spending model calls. Do not change the catalog or judge during execution. Per-run fingerprints let the report reject a mixed experiment.

Stock IDs are listed by `scenarios.py list`; setting SCENARIO_FILE adds custom IDs to that listing. Never put the reference implementation or test assertions into `spec` unless they are intentionally part of the task shown to both workflows.

For several repositories, use separate repository adapters and experiment directories, then account for repository clustering in the analysis. That broader adapter work is not included here. More repeats of a few small tasks do not establish general significance; see METHODOLOGY.md.

## Token-only Jira projects

The separate Jira importer emits `evaluation_mode: "tokens-only"` catalogs. These may use `kind: "change"`, empty held-out tests, and empty acceptance criteria when missing in Jira. Execution requires PROJECT_CONFIG and explicit review/execution controls; independent correctness remains unverified. See [JIRA_BENCHMARK.md](JIRA_BENCHMARK.md). The graded schema above remains unchanged.
