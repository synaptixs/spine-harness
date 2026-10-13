# Portable handover validation — v20

The v20 source changes standalone framework setup. A new four-arm configuration
resolves the highest stable Spec Kit Git tag to a full commit and installs the
current npm `@latest` OpenSpec release. The exact Spec Kit source and observed
OpenSpec CLI version are saved before benchmark preparation. Reference-study
`setup.sh` writes the same pins to `WORK_DIR/framework-tools.json` and reuses
them on subsequent setup calls. The bundled Spine tools revision remains
`v3.57.1` (`a8952c1a14fc31601fb5721b77b61e36003287e3`).

## Offline verification on macOS

- `ruff check .` passed with Ruff 0.16.10.
- The CI test selection passed: 97 tests, 1 skipped, 4 subtests passed.
- macOS and Windows/WSL2 v20 archives built from the pinned Spine source.
  Both outer SHA-256 checks and ZIP integrity checks passed. Both packages
  contain `framework_tools.py`, its offline tests, and the updated quick start.

The live latest-release download and global OpenSpec install were not executed
as part of this offline validation. No model benchmark was run. The Windows
archive still needs validation on a WSL2 recipient machine before claiming
Windows setup works end to end. The historical v19 run and its fixed pins are
documented in [the v19 record](RELEASE_VALIDATION_V19.md).
