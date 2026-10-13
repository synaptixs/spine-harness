# Historical two-arm Jira run on macOS

Use this guide only to reproduce the older Spec Kit versus Spine + PKG Jira protocol. For the current one-issue four-arm pilot, start with [the macOS quick start](QUICKSTART.md).

## 1. Open the package

Unzip the archive and open the extracted **spineharness-macos** folder as a local project in the Codex app. Use a normal local chat in this folder.

You need your own ChatGPT account, a local checkout of your Python application, and read access to the selected Jira issues. The package includes the pinned Spine tools bundle. Git, Python 3.12, `uv`, and the Codex CLI must be available. Ask Codex to help install missing prerequisites; no benchmark is started by installation.

## 2. Historical two-arm prompt

Replace the four bracketed values:

> Read AGENTS.md and docs/portable/macos/TWO_ARM_JIRA.md. Prepare and run this harness on macOS using my repository at **[absolute repository path]**, baseline **[commit/tag, or HEAD]**, Jira site **[https://team.atlassian.net]**, and issues **[TEAM-123]**. Use the connected Jira read tool to save the selected requirements as JSON snapshots. Configure the application's dependencies and meaningful offline regression checks from its existing setup, plus a frozen issue-specific required-behavior check that fails on the baseline and can pass after implementation. Use my own ChatGPT sign-in, gpt-6-sol/high, one pass per workflow and a fresh run name. I authorize sending those selected Jira requirements and relevant disposable repository code to OpenAI/ChatGPT for this benchmark, and proceeding through routine spec-kit checklist gates while recording unchecked items. Prepare the same required baseline for both arms, then run through completion, report failures honestly, and generate the final report, results and evidence archive. Do not change my source checkout or Jira. Do not start another full attempt or repair failed acceptance checks automatically. Keep me updated at least every 15 minutes.

Codex will create `benchmark.json`, obtain the issue snapshots, prepare dependencies and check the baseline. If Jira is not connected, connect your own Jira integration or provide saved issue JSON responses shaped like `examples/jira_issue.example.json`. Use the full issue key, title and description; configure a separate acceptance field if your Jira uses one. No Jira token needs to be pasted into this chat or stored in the package.

If an issue depends on another change, Codex must resolve that prerequisite equally for both arms before measurement, or explain that the chosen baseline is unsuitable. It must not quietly use one arm's output as the other's starting point. Start with one issue; use a fresh run name for each additional issue unless all selected issues share the same frozen behavior checks.

## 3. Complete sign-in, then let it run

The harness's `login` command opens the normal sign-in flow. Sign in with **your** ChatGPT account when prompted. The dedicated login directory defaults to `~/.codex-spineharness`, outside the archive and results. Nothing copies the author's credentials.

Codex may request permission for dependency downloads, model networking, or macOS `sandbox-exec` checks outside its outer command sandbox. The model's project checks still run offline with writes limited to disposable copies. Keep the Mac awake during the run.

When it finishes, open:

- `results/<run-name>/deliverables/FINAL_REPORT.html` — readable report.
- `FINAL_REPORT.md`, `RESULTS.csv`, `RESULTS.json`, `USAGE.json` — report and data.
- `ARTIFACTS.md` — planning documents, code patches and test evidence.
- `results-and-artifacts.zip` and `.sha256` — portable output bundle.

The archive contains no prior Jira issues or application results. All output from your selected issues is written under your fresh `results/<run-name>/` directory.

## Commands Codex will use

Run from the extracted directory; the app can run these for you. First copy `benchmark.example.json` to `benchmark.json` and fill in real values.

```bash
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m spineharness.portable_benchmark doctor
python3 -m spineharness.portable_benchmark bootstrap --config benchmark.json
python3 -m spineharness.portable_benchmark login --config benchmark.json
python3 -m spineharness.portable_benchmark prepare --config benchmark.json
python3 -m spineharness.portable_benchmark run --config benchmark.json --approved --approve-checklist
```

`bootstrap` installs the pinned Spine tool environment. `prepare` makes a separate target clone, freezes requirements and runs baseline checks without model calls. `run` is the spending step; `--approved` records baseline review and consent for the chosen data transfer. Use `--approve-checklist` only when the user has authorized routine checklist continuation, as in the prompt above. Omitting it preserves spec-kit's native pause.

To use a local authorized Spine checkout instead of cloning its default URL:

```bash
python3 -m spineharness.portable_benchmark bootstrap --config benchmark.json --spine-source /path/to/spine
```

To regenerate reports after a closed run, without new model calls or repeating audits:

```bash
python3 -m spineharness.portable_benchmark report --config benchmark.json
```

To verify package integrity before setup:

```bash
shasum -a 256 -c SHA256SUMS
```

## If a run fails

Inspect `results/<name>/batch.log`, workflow logs, `JOB_FAILED`, and `QUOTA_STOP`. Reports preserve known usage and mark missing usage unknown. A timeout, quota failure, missing model, missing dependency or checklist pause is not a passing result. Do not delete markers and rerun over existing evidence. Diagnose first and choose a new name/paths for an explicitly requested new attempt. This package does not promise generic checkpoint resume.

See [CONFIGURATION.md](CONFIGURATION.md) for dependency settings, optional acceptance checks and terminal MCP import. No stock-scenario run is required before your Jira issues.

Official guidance checked for this handover: [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) and [authentication, dedicated credential storage and device login](https://learn.chatgpt.com/docs/auth). The tested benchmark CLI was 0.157.0; record the actual installed version. A changed CLI may change overhead or reject flags, so retain that difference in the experiment metadata.

## Required behavior setup for Spine 3.57.1

The default `require_behavior: true` requires a nonempty `.spine/required-behavior.yaml` containing at least one required check. The manifest and executable checks must already exist in the selected baseline, or be supplied through `behavior_files`. `prepare` adds supplied files only to a common disposable baseline and records its patch; the original repository stays unchanged. Both workflows receive that baseline.

Example configuration fragment (provide these files with real issue-specific assertions):

```json
{
  "require_behavior": true,
  "behavior_files": {
    ".spine/required-behavior.yaml": "inputs/required-behavior.yaml",
    "checks/check_required_behavior.py": "inputs/check_required_behavior.py"
  },
  "behavior_protected_files": [],
  "max_refine": 3,
  "max_judge_revisions": 2,
  "max_model_calls": 24
}
```

Manifest example:

```yaml
requirements:
  - id: issue-default-behavior
    description: State the Jira requirement and expected observable output
    command: [python3, checks/check_required_behavior.py]
    timeout: 60
    required: true
```

Write assertions that fail on the unsolved baseline and pass only when the requested behavior works. Keep regression `checks` passing on the prepared baseline; do not put the intentionally failing new behavior check in that list. List fixture/support files in `behavior_protected_files` when they are not directly named by a command. Existing `test_*.py` files, the manifest and directly named check scripts are protected automatically.

Public behavior failures feed native refinement. Hidden `acceptance_tests` remain outside model access and run after closure with no feedback. If two issues require different public checks, use separate run configurations and fresh names, one per issue. Internal native refinements are part of the measured workflow; post-audit repairs remain separate.

`max_refine` is a per-category native allowance, not a total call count. `max_model_calls` bounds all native calls, including semantic review and model retries. Project dependencies are prepared once; automatic dependency installation during measurement is disabled. A missing optional type-checker is reported by Spine as skipped. Install required tooling before preparation and include mandatory quality checks in `checks`.

For explicitly chosen legacy token-only experiments, `require_behavior: false` permits an absent manifest and reports behavior as unverified. It does not certify completion. Stock scenarios use a separate path; `benchmark.py` is the Jira/repository entry point.
