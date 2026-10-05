# Release validation — 2026-10-04

This macOS release was extracted into a fresh folder whose path contains spaces and checked there.

- 42 offline tests passed: 7 portable reporting/configuration tests, 8 Jira/disposable-clone tests, 2 usage-report tests, and 25 Codex adapter/scenario tests.
- Every packaged file matched SHA256SUMS; ZIP integrity, packaged JSON and audit XML parsing passed.
- The prerequisite check passed. Preparation cloned a small committed Python application, imported a fictional TEAM-12 Jira snapshot, validated the frozen catalog, and passed a real offline macOS sandbox baseline test. The original sample checkout fingerprint was unchanged.
- Both workflow command plans passed a dry run against the new issue. No model calls were made.
- A frozen external acceptance test ran in the disposable sample repository and generated passing JSON, log and JUnit XML artifacts.
- The new report generator was checked against a copy of the completed benchmark evidence. It reproduced the recorded spec-kit subtotal of 11,741,696 tokens and $4.146632 API list-price equivalent, while leaving the failed Spine attempt incomplete with unknown consumption.
- Reporting tests verified successful and incomplete output bundles, response deduplication, portable ledger reconciliation, active-run refusal, credential-pattern rejection and symlink exclusion.
- Every relative artifact link in the included final comparison report resolved inside the package. Historical machine-local locations are marked as historical placeholders.

The included ONTM-4 study is prior live evidence. Packaging validation did not run another paid benchmark, perform a fresh account login, fetch live Jira issues or install dependencies on a second physical Mac. The recipient must supply their own account access and repository dependencies. Live results on other issues are not promised by these offline checks.
