# spec-kit vs Spine + PKG — Codex subscription harness

External handover, 2026-09-30-v6. Start with **[QUICKSTART.md](QUICKSTART.md)**.

This harness runs both workflows through the Codex CLI using the recipient's own
ChatGPT sign-in. No OpenAI API key is needed in the default configuration. It can
be launched from a terminal or from a local Codex app project.

The archive contains the harness and instructions, not the Spine repository, model
credentials, installed dependencies, or the author's results. Recipients need access
to the pinned Spine repository and a Codex account with the selected model available.
Repository access must be arranged separately if their Git account cannot clone it.

| Item | Default / tested value |
|---|---|
| Model | `gpt-6-sol`, high reasoning |
| Codex CLI tested | `0.157.0` |
| Python | 3.12 |
| uv tested | 0.8.0 |
| Target commit | `bd16dbb7d2451bfaffa94c02946972050e23a610` |
| Spine implementation | `v3.52.0` (`6c0454bac2dbb539665402d31e57e763db2d206a`) |
| spec-kit | `v1.0.11` |
| Corrected held-out suite | `a6ac7c34`, applied by `heldout_fix.py` |
| Platforms | Tested on macOS; Bash-based Linux/WSL execution is unverified |

## Included

- `setup.sh`, `env.example`: dependencies and isolated worktree setup.
- `run_comparison.py`, `speckit_codex.py`, `spine_pkg.py`, `spine_intake.py`: runners.
- `codex_llm.py`, `codex_usage.py`, `codex_protocol.py`: completion adapter and accounting.
- `summarize.py`: descriptive outcomes and legacy exploratory comparison tables.
- `report_usage.py`: portable token/cost report from exported per-response ledgers.
- `scenario_catalog.py`, `scenarios.py`, `examples/`: extensible scenarios and held-out tests.
- `report_results.py`: matched scenario/repeat reporting.
- `test_codex_backend.py`, `test_report_usage.py`, `test_scenarios.py`: checks that make no model calls.
- `CODEX_RUN.md`, `METHODOLOGY.md`: implementation details and interpretation limits.
- `MANIFEST.json`, `SHA256SUMS`: package versions and file integrity checks.

The intended flow is a default 33-scenario reference benchmark, followed by actual Jira issues in the team's own application repository. QUICKSTART.md includes a fictional Jira mapping, held-out test example, and repository adapter requirements. An experimental Python application adapter and read-only Jira importer are now included; see **[JIRA_BENCHMARK.md](JIRA_BENCHMARK.md)**. They have offline checks but no live Jira/model validation yet.

The default selects the original three stock tickets plus 30 new tasks (15 edits, 15 creates). `catalog/INDEX.md` lists them; `profiles/pilot.env` selects the optional one-ticket smoke pilot. The ten built-ins plus 30 bundled additions provide 40 selectable IDs, and `SCENARIO_FILE` can add JSON-defined scenarios with separate held-out tests. See **[SCENARIOS.md](SCENARIOS.md)** and `examples/scenarios.json`. `scenarios.py` lists and validates catalogs; `report_results.py` produces paired scenario-level summaries for arbitrary catalog sizes. The default remains the pinned Spine reference target. External Python repositories use the separate token-only project mode; they do not inherit the reference study's grading claims.

## Status

Both subscription workflows completed an 18-run stock study on GPT-6 Sol, including explicitly approved checklist continuations and one recorded provider-capacity recovery. This package's new catalog extension and edit-file detection were checked with unit tests, real pinned catalogs, sample judge positive/negative cases, and clean-extraction dry runs. New custom scenarios have not been run against a live model for this release.

The new adapter changes the model interface and overhead. Results should be identified
as **Codex subscription adapter** results, not pooled with historical direct-API runs.
Dollar figures are API list-price equivalents, not subscription invoices.

The archive also retains the original optional API/Claude runners for reference; that
route is not the validated handover path. No third-party repository or package is vendored.
Use those dependencies under their own access requirements and licenses.
