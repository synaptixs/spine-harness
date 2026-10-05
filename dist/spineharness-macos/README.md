# Jira benchmark harness for the Codex app

Start with **[QUICKSTART.md](QUICKSTART.md)**. Unzip, open this folder as a local project in Codex, and paste the supplied prompt with your repository and Jira keys.

This macOS package compares **spec-kit and Spine + PKG** on disposable copies of your Python application. Both use your own ChatGPT sign-in through the Codex CLI. Jira imports are read-only. Your source checkout is not where models work, and nothing pushes or writes to Jira.

**[Read the included final ONTM-4 report](reference/results/ontm4-benchmark-20260930/COMPARISON_REPORT.md).** It includes the measured post-audit Spine continuation. Original failures, repaired results, selected-check limits, and unknown earlier usage remain visible. This reference study is evidence of one case, not an expected result for your issues.

## What is included

- `benchmark.py`: setup, login, preparation, execution, and report regeneration.
- `deliverables.py`: closed-run reporting, deduplicated token accounting, optional frozen acceptance checks, artifact inventory, checksums and evidence ZIP generation.
- Native workflow wrappers, Jira importer, project sandbox adapter, and offline regression tests.
- `benchmark.example.json`, a short Codex prompt and configuration guide.
- `reference/results/`: final report, machine-readable results, plans, proposed patches, validation output and response-only token ledgers from the completed study.
- `MANIFEST.json` and `SHA256SUMS`: integrity checks for this release.
- `VALIDATION.md`: checks performed and remaining external-machine setup requirements.

After a run, open `results/<name>/deliverables/FINAL_REPORT.html`. The same directory contains Markdown, CSV, JSON, usage totals, an artifact inventory and `results-and-artifacts.zip` with a checksum. Reports also cover partial and failed runs.

The archive does not include credentials, private login caches, installed environments or a vendored Spine repository. The recipient needs authorized access to Spine and their application repository. The pinned workflow is Spine v3.52.0, commit `6c0454bac2dbb539665402d31e57e763db2d206a`, and spec-kit v1.0.11. Default model is gpt-6-sol/high; model access is account-dependent. No paid benchmark is launched while unpacking or installing.

This release supports macOS and Python applications. Linux, WSL, Windows, and non-Python applications require a separate validated adapter. Full correctness is not inferred from generated tests. Optional frozen acceptance suites provide selected behavior evidence; post-audit repairs must be measured separately.

Full model conversations remain in each new run's local result directory. Portable evidence bundles contain a response-only usage ledger and omit full conversations and credentials. Rates are a frozen API list-price snapshot, not subscription invoices. Four earlier reference calls have unknown consumption and are not treated as free.
