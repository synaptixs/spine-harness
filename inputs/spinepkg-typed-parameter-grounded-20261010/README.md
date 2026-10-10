# SPKG-1 grounded replay input

This is a new matched attempt. The original run and its inputs remain unchanged.
The shared task names `RepoCodeExtractor.extract` as the public entry point;
all four arms receive the same task. The independent acceptance test stays
outside their application clones.

Before `prepare`, set these absolute local paths in the environment:
`SPKG_SOURCE_REPO`, `SPKG_APP_PYTHON`, `SPKG_CODEX_LOGIN_HOME`,
`SPKG_SPINE_TOOLS_DIR`, `SPKG_WORK_DIR`, and `SPKG_RESULTS_DIR`.
The last two must be unused, separate directories. Put the pinned OpenSpec
1.14.1 CLI on `PATH`.

Preparation makes no model calls. It must show passing baseline regressions,
independent acceptance failing on the unfixed baseline, independent acceptance
passing at the known fix, and `RepoCodeExtractor.extract` present in pinned
Spine's model context. A fresh model-spending run requires separate authorization.
