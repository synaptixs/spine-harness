# Jira benchmark harness for the Codex app

Start with [MATRIX_QUICKSTART.md](../../MATRIX_QUICKSTART.md): one repository, one issue, four workflows. The [default reference matrix](../../REFERENCE_MATRIX.md) schedules 33 scenarios across spec-kit, OpenSpec, Spine + PKG + OpenSpec, and Spine + PKG: 132 measurements per pass. Follow [REFERENCE_QUICKSTART.md](../../QUICKSTART.md) for that later run. The [single-task framework matrix](../../FRAMEWORK_MATRIX.md) supports the same four workflows plus external adapters on a frozen Jira or SWE-bench task. The older two-arm benchmark remains available for reproducibility.

> **v21:** The four-arm path pins published Spine 3.57.1 (`a8952c1a`), supplied as a Git bundle. Setup resolves current Spec Kit and OpenSpec releases and freezes their versions. The matrix doctor checks local setup and an optional model smoke before measurement. The separate two-arm Jira benchmark also defaults to Spine 3.57.1; configure issue-specific public behavior checks before preparation. The matched implementation-only path is documented in [CONTEXT_MATRIX.md](../../CONTEXT_MATRIX.md).

Start with **[QUICKSTART.md](QUICKSTART.md)**. The extracted package also has a top-level `QUICKSTART.md` that links here. Unzip, open the package folder as a local project in Codex, and paste the four-arm prompt with your repository and issue. For the older two-arm Jira path, use [TWO_ARM_JIRA.md](TWO_ARM_JIRA.md).

The one-issue matrix compares **spec-kit, OpenSpec, Spine + PKG + OpenSpec, and Spine + PKG** on disposable copies of your Python application. All four use your own ChatGPT sign-in through the Codex CLI. Jira imports are read-only. Your source checkout is not where models work, and nothing pushes or writes to Jira.

This handover is intentionally clean: it contains no prior Jira snapshots, application source patches or benchmark results. Supply your own repository, issue snapshots and checks.

## What is included

- `src/spineharness/framework_matrix.py`: one-issue four-arm preparation, execution, reporting and result packaging.
- `src/spineharness/portable_benchmark.py`: historical two-arm setup, login, preparation, execution, and report regeneration.
- `src/spineharness/portable_deliverables.py`: closed-run reporting, deduplicated token accounting, optional frozen acceptance checks, artifact inventory, checksums and evidence ZIP generation.
- Native workflow wrappers, Jira importer, project sandbox adapter, and offline regression tests.
- `examples/framework-matrix.example.json`, a one-issue start guide and configuration guide.
- `release_assets/spine-tools-v3.57.1.bundle`: reproducible pinned Spine tools checkout; target application source is separate.
- `examples/jira_issue.example.json`: the minimum shape of a saved Jira issue response.
- `MANIFEST.json` and `SHA256SUMS`: integrity checks for this release.
- `VALIDATION.md`: checks performed and remaining external-machine setup requirements.

After a run, open `results/<name>/deliverables/FINAL_REPORT.html`. The same directory contains Markdown, CSV, JSON, usage totals, an artifact inventory and `results-and-artifacts.zip` with a checksum. Reports also cover partial and failed runs.

The archive does not include credentials, private login caches, or installed environments. It **does include** a Git bundle of Spine 3.57.1 for both paths; the recipient still supplies their own application repository. A fresh setup resolves current stable Spec Kit and OpenSpec releases and records exact pins before measurement; v19's historical pilot used Spec Kit v1.0.11 and OpenSpec 1.14.1. Default model is gpt-6-sol/high; model access is account-dependent. No paid benchmark is launched while unpacking or installing.

This release supports macOS and Python applications. Linux, WSL, Windows, and non-Python applications require a separate validated adapter. Full correctness is not inferred from generated tests. Optional frozen acceptance suites provide selected behavior evidence; post-audit repairs must be measured separately.

Full model conversations remain in each new run's local result directory. Portable evidence bundles contain a response-only usage ledger and omit full conversations and credentials. Rates are a frozen API list-price snapshot, not subscription invoices. Missing usage is reported as unknown, never zero.
