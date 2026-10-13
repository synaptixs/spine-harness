# Harness guides

Start with [one issue across four workflows](MATRIX_QUICKSTART.md). The
[framework matrix reference](FRAMEWORK_MATRIX.md) describes its configuration,
preflight, execution, and reports.

- [Matched context comparison](CONTEXT_MATRIX.md)
- [33-scenario reference study](QUICKSTART.md) and [matrix reference](REFERENCE_MATRIX.md)
- [Scenario catalog](SCENARIOS.md)
- [Historical two-arm Jira workflow](JIRA_BENCHMARK.md)
- [macOS portable handover](portable/macos/QUICKSTART.md)
- [Windows with WSL2 handover](portable/windows/QUICKSTART.md)
- [Release validation](releases/RELEASE_VALIDATION_V19.md)

Run module commands from the repository or extracted archive root after setting
`PYTHONPATH="$PWD/src"`, or install the project with `python3 -m pip install -e .`.
The protected roadmap and superseded instructions are retained under `archive/`
in the source repository; they are not part of the active guides or portable
release.
