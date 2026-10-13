# Harness guides

Use the [qualification guide](MATRIX_QUICKSTART.md) for the first four-arm task.
The [framework matrix reference](FRAMEWORK_MATRIX.md) covers configuration,
preflight, execution, reporting, and [combining multiple issues](FRAMEWORK_MATRIX.md#compare-multiple-tasks).

- [Matched context comparison](CONTEXT_MATRIX.md)
- [33-scenario reference study](QUICKSTART.md) and [matrix reference](REFERENCE_MATRIX.md)
- [Scenario catalog](SCENARIOS.md)
- [Historical two-arm Jira workflow](JIRA_BENCHMARK.md)
- [macOS portable handover](portable/macos/QUICKSTART.md)
- [Historical two-arm macOS package instructions](portable/macos/TWO_ARM_JIRA.md)
- [Windows with WSL2 handover](portable/windows/QUICKSTART.md)
- [Build macOS and Windows/WSL2 archives](BUILD_RELEASES.md)
- [Release validation](releases/RELEASE_VALIDATION_V21.md)

Run module commands from the repository or extracted archive root after setting
`PYTHONPATH="$PWD/src"`, or install the project with `python3 -m pip install -e .`.
The protected roadmap and superseded instructions are retained under `archive/`
in the source repository; they are not part of the active guides or portable
release.
