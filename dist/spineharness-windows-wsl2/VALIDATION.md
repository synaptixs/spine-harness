# Windows / WSL2 release validation — 2026-10-04

This package targets Windows with WSL2 Ubuntu. Native Windows Python and WSL1 are unsupported. The PowerShell launcher forwards arguments to Linux Python without shell interpolation.

## Checks performed

- 48 offline tests passed on the build Mac: 8 portable reporting/configuration tests, 8 Jira/disposable-clone tests, 2 usage-report tests, 5 Linux/WSL sandbox-command tests, and 25 Codex adapter/scenario tests.
- The 23 portable/Jira/usage/WSL tests also passed from the extracted archive in a disposable Linux container with Python 3.12. The extraction path contained spaces.
- A real bubblewrap confinement probe verified writes inside the disposable repository, rejection of writes outside it (including through a symlink), and isolation from a host network listener.
- The Linux adapter prepared an independent sample Git clone and ran a real pytest baseline in its sandbox. The original source fingerprint remained unchanged.
- Frozen external acceptance tests ran for both simulated workflow summaries. JSON outcomes, test logs, JUnit XML, final HTML/Markdown reports, CSV/JSON results, usage ledger, artifact inventory, checksums and a valid evidence ZIP were generated. Those simulated summaries are test fixtures, not live model results.
- Package checksums, ZIP integrity, JSON/XML parsing, root Python syntax and the reference report's relative artifact links were verified. Credential-pattern and machine-specific-path checks passed.
- Windows-style UTF-8 BOM configuration is accepted; Windows drive paths and Windows Python interpreters are rejected with WSL guidance.

## What remains environment-dependent

The Linux sandbox validation used a Docker Linux environment on macOS, with nested namespace permissions enabled only for its disposable test container. It had no host mounts, network access or credentials during testing. Docker is not required by the delivered WSL2 package.

The PowerShell launcher has not been executed on a physical Windows/WSL2 host here. Windows policy, Ubuntu user-namespace/AppArmor policy, fresh recipient login, dependency installation and live Jira/model access still require recipient-machine verification. Run verify and doctor there before preparing or spending on a benchmark; doctor fails closed if confinement is unavailable. No paid model run was started during packaging.

The included completed ONTM-4 evidence is the historical macOS study, including the post-audit continuation. It is not a Windows performance result. API-equivalent price estimates use the packaged rate snapshot; unavailable usage remains unknown.
