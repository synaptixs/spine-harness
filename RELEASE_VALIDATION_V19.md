# Portable handover validation — v19

This source pins published Spine 3.57.1 at
`a8952c1a14fc31601fb5721b77b61e36003287e3`. Build the archive with
`python3 build_portable_release.py --spine-source /path/to/spine --output /path/to/dist`.
The builder verifies that the local checkout's `v3.57.1` tag resolves to the
pinned commit and puts a self-contained Git bundle in the archive. The bundle
is generated during packaging and is not committed to this repository.

The four-workflow matrix and the matched four-context implementation runner
are separate protocols. Neither a successful workflow nor passing selected
checks establishes complete issue correctness. Keep their results separate.

Source validation on macOS with Python 3.12 and Spine 3.57.1: Ruff passed;
the offline CI and portable suite passed with 92 tests, one skip, and four
subtests. These checks made no benchmark model calls. The Windows/WSL2 path
has not been live validated on a recipient machine.

Both macOS and Windows/WSL2 archives built from the local pinned Spine tag.
All extracted files passed `SHA256SUMS`; all local Markdown links resolved.
The macOS archive's Git bundle cloned at the exact pinned commit. The ZIP
builder also verified archive CRCs. No model calls were made during packaging.

The archive excludes credentials, installed environments, target application
source, previous issue snapshots, benchmark results, and raw conversations.
The recipient supplies their application repository, issue snapshot,
independent acceptance checks, and Codex login. Reported dollars are API
list-price equivalents, not subscription charges.
