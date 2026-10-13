# Quick start — macOS

Run **one issue through four workflows**, in this order: Spine + PKG, Spine + integrated OpenSpec + PKG, standalone OpenSpec, and Spec Kit. The included example configuration uses this order. Each arm gets the same frozen issue, application commit, model settings, and independent checks in its own disposable clone. Start with a Python application; the native Spine adapters currently run Python application checks.

This guide starts from a portable ZIP and ends at a reviewable report. The [four-arm qualification guide](../../MATRIX_QUICKSTART.md) gives the full preflight and configuration details. The [33-scenario reference study](../../QUICKSTART.md) and [historical two-arm Jira guide](TWO_ARM_JIRA.md) are separate paths.

## 1. Build or open the macOS package

If you already have the v21 ZIP and its `.sha256` file, verify and extract them in a fresh directory:

```bash
cd /path/to/archive-directory
shasum -a 256 -c spineharness-macos-2026-10-13-v21.zip.sha256
demo_dir="$HOME/SpineHarness-v21"
mkdir -p "$demo_dir"
unzip -q spineharness-macos-2026-10-13-v21.zip -d "$demo_dir"
cd "$demo_dir/spineharness-macos"
shasum -a 256 -c SHA256SUMS
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
```

To build the ZIP from a Spine Harness source checkout first, use Python 3.12 and a local Spine checkout containing tag `v3.57.1`:

```bash
cd /path/to/spine-harness
PYTHONPATH="$PWD/src" python3.12 -m spineharness.build_portable_release \
  --platform macos --spine-source /absolute/path/to/spine --output dist
```

The package includes the pinned Spine tools as a Git bundle. It does **not** include an application repository, credentials, installed dependencies, or benchmark results. Building and extracting the ZIP make no model calls. See [release builds](../../BUILD_RELEASES.md) for checksums and the Windows/WSL2 package.

## 2. Gather one issue and its checks

Have these ready before running a model:

- The absolute path to an authorized local Python repository and its full **pre-fix commit SHA**.
- One saved issue JSON file, or a Jira/GitHub issue accessible through a read-only connection.
- Regression commands that pass on that commit and independent acceptance checks that fail for the missing behavior. Keep acceptance checks outside model worktrees.
- A Python interpreter with the application's locked dependencies, and a dedicated Codex CLI sign-in. The Codex app and CLI have separate sign-ins.

Use a fresh run name and directories for every attempt. Setup resolves current standalone Spec Kit and OpenSpec releases, then records exact versions before preparation. Spine's integrated OpenSpec path comes from the bundled Spine `v3.57.1`; it does not use the standalone OpenSpec CLI.

## 3. Run from the Codex app

Open the extracted `spineharness-macos` folder as a **local project** in the [Codex desktop app](https://learn.chatgpt.com/docs/app). Start a new local chat and replace the brackets in this prompt:

> Read AGENTS.md and docs/MATRIX_QUICKSTART.md. Run one four-arm pilot for my Python repository **[absolute path]** at pre-fix commit **[full SHA]** using issue **[absolute JSON path or issue key and read-only connection]**. Use a fresh name, the same task and model settings for all arms, and independently authored regression and acceptance checks. Install the latest standalone Spec Kit and OpenSpec tools through the documented setup command, freeze their versions, and use the bundled Spine tools for both PKG arms. Use my dedicated Codex CLI sign-in. Resolve consequential scope questions with my recorded answer or stop; do not invent one. I authorize sending this selected issue and relevant disposable repository code to the configured model for **one** four-arm run after preflight passes, including routine Spec Kit checklist continuation. Run doctor and prepare, review the frozen inputs, then run once and package the result. Preserve my source checkout and issue tracker. Report each arm's completion, native validation, independent acceptance, tokens, time, and API list-price equivalent cost, including failures and unknown usage.

Codex can perform the local setup and offline checks. The `run --approved` step spends model tokens; the prompt above authorizes that one attempt. If a setup defect makes the comparison invalid, stop before model calls and fix the preflight for a new attempt.

## 4. Or use the terminal

From the extracted package, follow [the qualification guide](../../MATRIX_QUICKSTART.md#1-unpack-and-verify-on-macos) to unpack the bundled Spine tools and prepare the application's Python environment. Copy and edit `examples/framework-matrix.example.json` for your one issue, then run:

```bash
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m spineharness.framework_tools --config framework-matrix.json
mkdir -p "$HOME/.codex-spineharness"
CODEX_HOME="$HOME/.codex-spineharness" codex login
python3 -m spineharness.framework_matrix doctor --config framework-matrix.json
python3 -m spineharness.framework_matrix prepare --config framework-matrix.json
# Review results/<name>/PREPARED.json and TASK.json before the model run.
python3 -m spineharness.framework_matrix run --config framework-matrix.json --approved
python3 -m spineharness.framework_matrix package --config framework-matrix.json
```

`doctor` and `prepare` make no model calls in this sequence. An optional `doctor --smoke-model --approved` makes one small, separately counted model call. The run command requires the chosen issue's data-transfer and model-use authorization. Do not reuse an existing work or results directory.

Open `results/<name>/COMPARISON_REPORT.html` and `RESULTS.md`, then inspect each arm's `RESULT.json`, checks, and patch. The shareable `comparison-results.zip` contains issue text and generated source, so review it before sharing. A failed arm under a valid protocol is a result; an invalid setup stops the comparison. For multiple issues or repositories, repeat with fresh configs and [combine compatible closed runs](../../FRAMEWORK_MATRIX.md#multiple-application-repositories).
