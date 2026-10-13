# Windows / WSL2 handover validation — v19

This package runs Python and Codex inside WSL2 Ubuntu, controlled from the Windows Codex app or a WSL terminal. Native Windows Python and WSL1 are unsupported. The four-workflow framework matrix and its multi-repository aggregation were exercised on two public repositories on macOS. **They have not yet been live-tested on a Windows/WSL2 recipient machine.**

The release build verifies file hashes, the bundled Spine 3.57.1 Git revision, archive CRC, and a credential-pattern scan. The recipient should run `python3 verify_package.py` inside Ubuntu, then the framework-matrix `doctor` and `prepare` steps with their own repository and interpreter before model work. `doctor` checks local tools and sandbox confinement; it does not prove application correctness. Keep all Python environments and CLI tools inside the same WSL2 distribution.

The first live Windows qualification should use one repository and one issue across the four workflows. Confirm all four measurements, source/task integrity, protected checks, usage ledgers, and acceptance results before adding more repositories. A model-generated implementation can fail acceptance while the harness itself completes successfully; report those outcomes separately.
