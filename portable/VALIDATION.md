# macOS handover validation — v19

Start with [MATRIX_QUICKSTART.md](MATRIX_QUICKSTART.md) and read [RELEASE_VALIDATION_V19.md](RELEASE_VALIDATION_V19.md) for the exact checks and limits. `SHA256SUMS` verifies the extracted archive files. The included Spine Git bundle reproduces the published 3.57.1 tools commit; the target application and its dependencies are supplied separately.

The public one-issue #456 pilot recorded four workflow rows, immutable original source and external acceptance input, stage-token reconciliation, and generated patches. It also recorded a genuine Spine + OpenSpec clarity stop and protected baseline test edits by two other arms. These are disclosed results, not a guarantee of an error-free run on a different issue. The full 33-scenario four-arm benchmark and an external-machine live run have not been completed.

No credentials, prior Jira snapshots, application patches, or model conversations are included in this handover. Dependency installation and model calls require recipient access. `prepare` must pass for the recipient's selected repository before any model run; `run` must use a fresh experiment name and explicit `--approved`.
