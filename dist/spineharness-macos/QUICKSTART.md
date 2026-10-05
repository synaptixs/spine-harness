# Quick start in Codex — macOS

## 1. Open the package

Unzip the archive and open the extracted **spineharness-macos** folder as a local project in the Codex app. Use a normal local chat in this folder.

You need your own ChatGPT account, access to the Spine repository, a local checkout of your Python application, and read access to the selected Jira issues. Git, Python 3.12, `uv`, and the Codex CLI must be available. Ask Codex to help install missing prerequisites; no benchmark is started by installation.

## 2. Paste this prompt

Replace the four bracketed values:

> Read AGENTS.md and QUICKSTART.md. Prepare and run this harness on macOS using my repository at **[absolute repository path]**, baseline **[commit/tag, or HEAD]**, Jira site **[https://team.atlassian.net]**, and issues **[TEAM-123, TEAM-456]**. Use the connected Jira read tool to save the selected requirements as JSON snapshots. Configure the application's dependencies and meaningful offline regression checks from its existing setup. Use my own ChatGPT sign-in, gpt-6-sol/high, one pass per workflow and a fresh run name. I authorize sending those selected Jira requirements and relevant disposable repository code to OpenAI/ChatGPT for this benchmark, and proceeding through routine spec-kit checklist gates while recording unchecked items. Prepare the same required baseline for both arms, then run through completion, report failures honestly, and generate the final report, results and evidence archive. Do not change my source checkout or Jira. Do not start another full attempt or repair failed acceptance checks automatically. Keep me updated at least every 15 minutes.

Codex will create `benchmark.json`, obtain the issue snapshots, prepare dependencies and check the baseline. If Jira is not connected, connect your own Jira integration or provide saved issue JSON responses. No Jira token needs to be pasted into this chat or stored in the package.

If an issue depends on another change, Codex must resolve that prerequisite equally for both arms before measurement, or explain that the chosen baseline is unsuitable. It must not quietly use one arm's output as the other's starting point. Start with one or two independent issues.

## 3. Complete sign-in, then let it run

The harness's `login` command opens the normal sign-in flow. Sign in with **your** ChatGPT account when prompted. The dedicated login directory defaults to `~/.codex-spineharness`, outside the archive and results. Nothing copies the author's credentials.

Codex may request permission for dependency downloads, model networking, or macOS `sandbox-exec` checks outside its outer command sandbox. The model's project checks still run offline with writes limited to disposable copies. Keep the Mac awake during the run.

When it finishes, open:

- `results/<run-name>/deliverables/FINAL_REPORT.html` — readable report.
- `FINAL_REPORT.md`, `RESULTS.csv`, `RESULTS.json`, `USAGE.json` — report and data.
- `ARTIFACTS.md` — planning documents, code patches and test evidence.
- `results-and-artifacts.zip` and `.sha256` — portable output bundle.

The included completed study is under `reference/results/`. Its final ONTM-4 report clearly distinguishes the original output from the post-audit continuation. These files are reference evidence, not inputs for your new issue.

## Commands Codex will use

Run from the extracted directory; the app can run these for you. First copy `benchmark.example.json` to `benchmark.json` and fill in real values.

```bash
python3 benchmark.py doctor
python3 benchmark.py bootstrap --config benchmark.json
python3 benchmark.py login --config benchmark.json
python3 benchmark.py prepare --config benchmark.json
python3 benchmark.py run --config benchmark.json --approved --approve-checklist
```

`bootstrap` installs the pinned Spine tool environment. `prepare` makes a separate target clone, freezes requirements and runs baseline checks without model calls. `run` is the spending step; `--approved` records baseline review and consent for the chosen data transfer. Use `--approve-checklist` only when the user has authorized routine checklist continuation, as in the prompt above. Omitting it preserves spec-kit's native pause.

To use a local authorized Spine checkout instead of cloning its default URL:

```bash
python3 benchmark.py bootstrap --config benchmark.json --spine-source /path/to/spine
```

To regenerate reports after a closed run, without new model calls or repeating audits:

```bash
python3 benchmark.py report --config benchmark.json
```

To verify package integrity before setup:

```bash
shasum -a 256 -c SHA256SUMS
```

## If a run fails

Inspect `results/<name>/batch.log`, workflow logs, `JOB_FAILED`, and `QUOTA_STOP`. Reports preserve known usage and mark missing usage unknown. A timeout, quota failure, missing model, missing dependency or checklist pause is not a passing result. Do not delete markers and rerun over existing evidence. Diagnose first and choose a new name/paths for an explicitly requested new attempt. This package does not promise generic checkpoint resume.

See [CONFIGURATION.md](CONFIGURATION.md) for dependency settings, optional acceptance checks and terminal MCP import. No 33-scenario reference run is required before your Jira issues.

Official guidance checked for this handover: [Codex CLI](https://learn.chatgpt.com/docs/codex/cli) and [authentication, dedicated credential storage and device login](https://learn.chatgpt.com/docs/auth). The tested benchmark CLI was 0.157.0; record the actual installed version. A changed CLI may change overhead or reject flags, so retain that difference in the experiment metadata.
