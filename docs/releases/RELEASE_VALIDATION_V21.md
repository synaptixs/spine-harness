# Portable handover validation — v21

This release makes the one-issue four-arm pilot the macOS package's main quick start and sets the example's arm order to Spine + PKG, Spine + integrated OpenSpec + PKG, standalone OpenSpec, then Spec Kit. The extracted package has a top-level `QUICKSTART.md` pointing to the full macOS guide. The older two-arm Jira procedure remains available at `docs/portable/macos/TWO_ARM_JIRA.md`. The tool protocol is unchanged from v20: a fresh setup freezes current standalone Spec Kit and OpenSpec versions; Spine `v3.57.1` remains bundled for both PKG arms.

## Offline verification on macOS

- `ruff check .` passed with Ruff 0.16.10.
- The CI test selection passed: 97 tests, 1 skipped, 4 subtests passed.
- The macOS and Windows/WSL2 v21 archives built from the pinned Spine source. Outer SHA-256 and ZIP integrity checks passed. The macOS archive contains the top-level quick start, full guide, and preserved historical guide; extracted `SHA256SUMS` passed.
- Local links in the updated guides resolved against the source or packaged layout.

No model benchmark was run. The Windows/WSL2 path still needs live validation on a recipient machine. Earlier model-run evidence and its limits remain in [the v19 record](RELEASE_VALIDATION_V19.md); [v20](RELEASE_VALIDATION_V20.md) records the standalone tool setup change.
