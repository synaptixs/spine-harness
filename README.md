# Four-workflow specification benchmark — Codex subscription harness

The [default reference matrix](REFERENCE_MATRIX.md) schedules all **33 scenarios** through spec-kit, OpenSpec standalone, Spine + PKG + OpenSpec, and Spine + PKG without OpenSpec: **132 ticket-arm measurements per pass**. The [single-task framework matrix](FRAMEWORK_MATRIX.md) supports the same four arms plus external adapters on Jira or official SWE-bench tasks. Historical two-arm results remain separate.

Current source: published Spine 3.57.1 in portable release v19. Historical results retain their original versions. For an external team's repository, start with **[MATRIX_QUICKSTART.md](MATRIX_QUICKSTART.md)**; for the separate 33-scenario reference study, use [QUICKSTART.md](QUICKSTART.md). For a matched implementation step using four reviewed framework contexts, see [CONTEXT_MATRIX.md](CONTEXT_MATRIX.md).

The default matrix runs all four workflows through the Codex CLI using the recipient's own
ChatGPT sign-in. No OpenAI API key is needed in the default configuration. It can
be launched from a terminal or from a local Codex app project.

The archive contains the harness, instructions, and a self-contained Git bundle of
Spine 3.57.1. It does not contain model credentials, installed dependencies,
the author's results, or the team's application repository. Recipients need a
Codex account with the selected model and authorized access to their application.

| Item | Default / tested value |
|---|---|
| Model | `gpt-6-sol`, high reasoning |
| Codex CLI tested | `0.157.0` |
| Python | 3.12 |
| uv tested | 0.8.0 |
| Target commit | `bd16dbb7d2451bfaffa94c02946972050e23a610` |
| Current Spine source for both runners | `v3.57.1` (`a8952c1a14fc31601fb5721b77b61e36003287e3`) |
| Earlier saved runs | Preserve their original 3.56.0 or pre-release pins; do not pool them with a 3.57.1 run |
| spec-kit | `v1.0.11` |
| Corrected held-out suite | `a6ac7c34`, applied by `heldout_fix.py` |
| Platforms | Tested on macOS; Bash-based Linux/WSL execution is unverified |

## Included

- `setup.sh`, `env.example`: dependencies and isolated worktree setup.
- `reference_matrix.py`, `framework_matrix.py`, `framework_spine_pkg.py`: four-arm reference and single-task runners.
- `run_comparison.py`, `speckit_codex.py`, `spine_pkg.py`, `spine_intake.py`: historical two-arm runners.
- `codex_llm.py`, `codex_usage.py`, `codex_protocol.py`: completion adapter and accounting.
- `summarize.py`: descriptive outcomes and legacy exploratory comparison tables.
- `report_usage.py`: portable token/cost report from exported per-response ledgers.
- `scenario_catalog.py`, `scenarios.py`, `examples/`: extensible scenarios and held-out tests.
- `report_results.py`: matched scenario/repeat reporting.
- `test_codex_backend.py`, `test_report_usage.py`, `test_scenarios.py`: checks that make no model calls.
- `CODEX_RUN.md`, `METHODOLOGY.md`: implementation details and interpretation limits.
- `MANIFEST.json`, `SHA256SUMS`: package versions and file integrity checks.

For a new team, the intended flow is one repository and one issue through the four-arm framework matrix, followed by further issues after checking the first report. The 33-scenario reference study is a separate, larger experiment. `JIRA_BENCHMARK.md` documents the two-arm Jira path; the four-arm issue path accepts a saved Jira JSON snapshot.

The default selects the original three stock tickets plus 30 new tasks (15 edits, 15 creates). `catalog/INDEX.md` lists them; `profiles/pilot.env` selects the optional one-ticket smoke pilot. The ten built-ins plus 30 bundled additions provide 40 selectable IDs, and `SCENARIO_FILE` can add JSON-defined scenarios with separate held-out tests. See **[SCENARIOS.md](SCENARIOS.md)** and `examples/scenarios.json`. `scenarios.py` lists and validates catalogs; `matrix_study.py` produces the four-arm aggregate. The default remains the pinned Spine reference target. External Python repositories use the separate framework-matrix path.

## Status

Both subscription workflows completed an 18-run stock study on GPT-6 Sol, including explicitly approved checklist continuations and one recorded provider-capacity recovery. This package's new catalog extension and edit-file detection were checked with unit tests, real pinned catalogs, sample judge positive/negative cases, and clean-extraction dry runs. New custom scenarios have not been run against a live model for this release.

The new adapter changes the model interface and overhead. Results should be identified
as **Codex subscription adapter** results, not pooled with historical direct-API runs.
Dollar figures are API list-price equivalents, not subscription invoices.

The archive also retains the original optional API/Claude runners for reference; that
route is not the validated handover path. The pinned Spine tools history is bundled;
other third-party packages are installed separately.
Use those dependencies under their own access requirements and licenses.

## Native completion update

Native Spine arms use `spine_feature.py` to call the production `run_feature` pipeline. Public behavior checks drive its bounded refinement; hidden acceptance checks remain post-run only. The historical `run_comparison.py` still uses `scripts/codegen_benchmark.py` and must not be pooled with the new matrix.
