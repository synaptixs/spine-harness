# Jira benchmark harness — Windows / WSL2

Start with **[QUICKSTART.md](QUICKSTART.md)**. Extract the ZIP, open the folder in the Windows Codex app, and paste the supplied prompt with your repository and Jira keys.

This version runs **spec-kit versus Spine + PKG inside WSL2 Ubuntu**, using your own ChatGPT account. `Run-Harness.ps1` forwards Windows commands to Linux. Application checks use bubblewrap with network isolation and writes restricted to disposable copies. The harness does not run under native Windows Python or WSL1.

Included:

- PowerShell launcher, simple Codex prompt, WSL setup instructions and configuration example.
- Harness, read-only Jira importer, disposable-clone adapter, sandbox self-test and regression tests.
- Automatic final HTML/Markdown report, JSON/CSV results, response-ledger token accounting and API-equivalent cost, test evidence, proposed patches, artifact inventory, checksums and output ZIP generation.
- The completed [ONTM-4 final reference report](reference/results/ontm4-benchmark-20260930/COMPARISON_REPORT.md), results, selected checks and artifacts, including the post-audit continuation. That study ran on macOS and retains first-run failures and unknown earlier usage.
- `SHA256SUMS`, `MANIFEST.json` and [VALIDATION.md](VALIDATION.md).

Both workflows use independent copies of the same committed application baseline and frozen Jira requirements. Default model: gpt-6-sol/high; Spine v3.52.0 at commit `6c0454bac2dbb539665402d31e57e763db2d206a`; spec-kit v1.0.11. Reports cover partial and failed runs. Unrecorded usage is unknown, not zero; API list-price equivalents are not subscription invoices.

Supports Python applications with offline checks. The recipient supplies authorized repository/Jira access, their own sign-in and application dependencies. No credentials, environments, full raw conversations or vendored Spine repository are included. See VALIDATION.md for the distinction between local tests, Linux sandbox validation and verification still needed on an actual Windows/WSL2 machine.
