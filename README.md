# Spine Harness

**Compare four specification-to-code workflows on the same software issue.** Spine Harness gives each workflow the same committed repository baseline, issue, model settings, and checks, then records what each one produced and whether configured independent acceptance passed.

![One frozen issue and repository feed four isolated workflows, whose results are checked and compared](docs/assets/harness-overview.svg)

## The four workflows

| Workflow | Context used for implementation |
| --- | --- |
| **Spine + PKG** | Spine's Product Knowledge Graph grounds the native feature workflow. |
| **Spine + integrated OpenSpec + PKG** | Spine's feature workflow also uses its integrated OpenSpec path. |
| **OpenSpec** | Standalone OpenSpec workflow. |
| **Spec Kit** | Standalone spec-kit workflow. |

Each arm works in a separate disposable copy of the target repository. The report keeps workflow completion, Spine's native validation, regression checks, independent acceptance, changed protected checks, tokens, time, and API list-price equivalent cost distinct. A passing check covers the selected behavior; it does not certify the whole issue.

## Start with one repository and one issue

1. **Set up the tools.** Follow the [macOS handover](docs/portable/macos/QUICKSTART.md) or [Windows/WSL2 setup](docs/portable/windows/SETUP_WSL.md). The harness uses Python 3.12, Git, uv, OpenSpec, a pinned Spine tools checkout, and a Codex CLI sign-in with access to the chosen model.
2. **Freeze the task.** Copy [the four-arm example configuration](examples/framework-matrix.example.json) to `framework-matrix.json`. Set `source_repo`, a pre-fix `baseline` commit, one saved issue in `task_file`, the application's Python interpreter, and `required_grounding`. Configure regression `checks` that pass on the baseline and independent `acceptance_checks` that expose the missing behavior. The [one-issue guide](docs/MATRIX_QUICKSTART.md) walks through this; the [framework configuration reference](docs/FRAMEWORK_MATRIX.md) explains the fields.
3. **Check before spending model tokens.** Run `doctor` to verify the local tools, then `prepare` to freeze the task and check the baseline. The optional `doctor --smoke-model --approved` makes a small model call. Review the prepared evidence before starting the four arms.
4. **Run once and inspect the evidence.** Follow the [run and report steps](docs/MATRIX_QUICKSTART.md#3-sign-in-prepare-then-run). The result directory contains a comparison report, per-arm outcomes, generated patches, usage evidence, and a shareable archive. A setup defect stops the comparison; a workflow failure under a valid setup remains a reported result.

From a source checkout, set `PYTHONPATH="$PWD/src"` before running `python3 -m spineharness.framework_matrix`. The [documentation index](docs/README.md) covers the packaged archives and all other commands. The original application checkout and issue tracker are read-only during measurement.

## Other study modes

- [33-scenario reference matrix](docs/QUICKSTART.md): a larger four-arm study after the one-issue pilot.
- [Matched context comparison](docs/CONTEXT_MATRIX.md): vary framework context while holding the implementation step fixed.
- [Scenario catalog](docs/SCENARIOS.md): add or validate reference tasks and held-out checks.
- [Historical two-arm Jira workflow](docs/JIRA_BENCHMARK.md): reproduce the earlier protocol without pooling its results with the four-arm matrix.

Current runtime and release validation details are in the [release notes](docs/releases/RELEASE_VALIDATION_V19.md). Harness modules live in `src/spineharness/`, offline tests in `tests/`, and current guides in `docs/`.
