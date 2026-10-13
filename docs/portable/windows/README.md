# Jira benchmark harness — Windows / WSL2

For an external repository, start with the [one-issue, four-workflow pilot](QUICKSTART.md) using spec-kit, OpenSpec, Spine + PKG + OpenSpec, and Spine + PKG. The [33-scenario reference matrix](../../REFERENCE_MATRIX.md) is a separate, larger run. The [framework matrix](../../FRAMEWORK_MATRIX.md) also supports external command adapters and SWE-bench tasks. All four-workflow commands run inside WSL2 Ubuntu. The PowerShell launcher still covers the older two-arm Jira path.

> **v19:** The bundled tools pin Spine 3.57.1 at `a8952c1a14fc31601fb5721b77b61e36003287e3`. The multi-repository matrix was exercised on macOS; the Windows/WSL2 path still requires live validation on a recipient machine.

Start with **[QUICKSTART.md](QUICKSTART.md)**. Extract the ZIP, open the folder in the Windows Codex app, and paste the supplied prompt with your repository and Jira keys.

The four-workflow matrix uses your own ChatGPT account inside WSL2 Ubuntu. `Run-Harness.ps1` forwards the historical two-arm commands to Linux. Application checks use bubblewrap with network isolation and writes restricted to disposable copies. The harness does not run under native Windows Python or WSL1.

Included:

- PowerShell launcher, simple Codex prompt, WSL setup instructions and configuration example.
- Harness code in `src/spineharness/`, read-only Jira importer, disposable-clone adapter, sandbox self-test and regression tests in `tests/`.
- Automatic final HTML/Markdown report, JSON/CSV results, response-ledger token accounting and API-equivalent cost, test evidence, proposed patches, artifact inventory, checksums and output ZIP generation.
- `examples/jira_issue.example.json`, a generic Jira issue snapshot example. No prior issues, source patches or results are bundled.
- `SHA256SUMS`, `MANIFEST.json` and [VALIDATION.md](VALIDATION.md).

All four workflows use independent copies of the same committed application baseline and frozen issue requirements. Default model: gpt-6-sol/high; bundled Spine v3.57.1; spec-kit v1.0.11. Reports cover failed runs. Unrecorded usage is unknown, not zero; API list-price equivalents are not subscription invoices.

Supports Python applications with offline checks. The recipient supplies authorized repository/Jira access, their own sign-in and application dependencies. No credentials, environments, full raw conversations or vendored Spine repository are included. See VALIDATION.md for the distinction between local tests, Linux sandbox validation and verification still needed on an actual Windows/WSL2 machine.
