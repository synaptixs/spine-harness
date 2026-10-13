# Quick start — Windows with WSL2

> **Toolchain:** Setup resolves current stable Spec Kit and standalone OpenSpec releases and freezes their versions per attempt. Spine `v3.57.1` supplies both PKG arms, including its integrated OpenSpec path. [The tool table](../../MATRIX_QUICKSTART.md#tools-and-versions) explains each arm and future adapter options. The four-workflow matrix has been exercised on macOS, but not yet live-validated under WSL2.

For an external repository, run **one issue through all four workflows first**. Install WSL2 as below, then follow [MATRIX_QUICKSTART.md](../../MATRIX_QUICKSTART.md) and [FRAMEWORK_MATRIX.md](../../FRAMEWORK_MATRIX.md) inside Ubuntu. In the matrix guide, use `sha256sum -c SHA256SUMS` in place of the macOS `shasum` command, and use Linux paths and Linux interpreters throughout. Resolve OpenSpec and Spec Kit inside Ubuntu with the framework setup command. For the separate default 33-scenario study, see [REFERENCE_QUICKSTART.md](../../QUICKSTART.md) and [REFERENCE_MATRIX.md](../../REFERENCE_MATRIX.md). The `Run-Harness.ps1` commands below describe the older two-arm Jira path, not the four-workflow matrix.

This archive runs the harness in **WSL2 Ubuntu**, controlled from the **Windows Codex app**. It supports Python applications. Native Windows Python and WSL1 are not supported by this harness.

## Demo: build, install, and open in Codex

On a packaging Mac with a Spine Harness source checkout, Python 3.12, and a local Spine checkout containing tag `v3.57.1`, build the Windows/WSL2 ZIP. If you received the ZIP, start with the Ubuntu extraction step. The [release build guide](../../BUILD_RELEASES.md) has both platform commands.

```bash
cd /path/to/spine-harness
export PYTHONPATH="$PWD/src"
python3.12 -m spineharness.build_portable_release \
  --platform windows --spine-source /absolute/path/to/spine --output dist
(cd dist && shasum -a 256 -c spineharness-windows-wsl2-2026-10-13-v20.zip.sha256)
```

The ZIP is the distribution; there is no separate installer. Copy it and its checksum file to the Windows machine's Downloads folder. If WSL2 Ubuntu is missing, run `wsl --install -d Ubuntu` in Administrator PowerShell and restart if requested. Install the Linux prerequisites in [SETUP_WSL.md](SETUP_WSL.md). In an **Ubuntu shell**, verify and extract the ZIP on the Linux filesystem (replace `<windows-user>` with your Windows username):

```bash
(cd "/mnt/c/Users/<windows-user>/Downloads" && sha256sum -c spineharness-windows-wsl2-2026-10-13-v20.zip.sha256)
mkdir -p "$HOME/code/spineharness-demo"
cd "$HOME/code/spineharness-demo"
unzip "/mnt/c/Users/<windows-user>/Downloads/spineharness-windows-wsl2-2026-10-13-v20.zip"
cd spineharness-windows-wsl2
python3 verify_package.py
```

In the [Windows Codex app](https://learn.chatgpt.com/docs/windows/windows-app), set the agent environment to **Windows Subsystem for Linux** and restart the app. Add a local project for the extracted `spineharness-windows-wsl2` folder. You can reach it from the folder picker through `\\wsl$\Ubuntu\home\<ubuntu-user>\code\spineharness-demo\spineharness-windows-wsl2` (adjust the distribution and username). Start a new local chat and fill in the four-workflow prompt below with **Linux paths** for your repository and issue. Run harness commands inside Ubuntu with Python 3.12 and `PYTHONPATH` pointing to the extracted `src/` folder, as [the qualification guide](../../MATRIX_QUICKSTART.md) shows. The app and the Codex CLI inside Ubuntu use separate sign-ins; complete the CLI login when the setup guide asks. Building, extracting, and verifying the package make no model calls. A live four-arm run consumes model tokens and requires the selected task and authorization in the prompt. The WSL2 path still needs live validation on a recipient machine.

## Run a four-workflow issue in Codex

Replace the bracketed values:

> Read AGENTS.md, docs/portable/windows/QUICKSTART.md, docs/portable/windows/SETUP_WSL.md, docs/MATRIX_QUICKSTART.md and docs/FRAMEWORK_MATRIX.md. Set up the four-workflow framework matrix **inside WSL2 Ubuntu** for my Python repository at **[Linux/WSL repository path]**, committed baseline **[commit/tag or HEAD]**, and one saved issue **[TEAM-123]** from **[Jira site or public issue URL]**. Use read-only issue access, an isolated Codex CLI sign-in with my own ChatGPT account, gpt-6-sol/high, and one pass per workflow. Install the pinned OpenSpec CLI and bundled Spine 3.57.1 tools. Configure actual Linux application dependencies, baseline regression commands, and an external issue-specific acceptance command that fails on the baseline. Freeze the issue and checks, run `python3 -m spineharness.framework_matrix doctor` and `prepare`, then run all four arms once with a fresh name and package the closed result. I authorize sending the selected issue and relevant disposable repository code to OpenAI/ChatGPT for this benchmark and routine spec-kit checklist continuation. Preserve the source checkout and issue tracker; do not repair measured outputs, silently rerun an arm, or launch a duplicate full attempt. Report workflow status separately from acceptance, protected-test changes, tokens, wall time and API list-price-equivalent cost.

Codex handles setup and execution. You may need to complete the Linux administrator password prompt, sign in to ChatGPT, and allow commands through the app's normal permissions. Your own authorized access to the application repository and selected issue is required. Start with one issue; use a fresh run name for each additional issue.

## Open your results

For the four-workflow matrix, outputs are in `results/<name>/` under the extracted folder:

- `COMPARISON_REPORT.html` and `COMPARISON_REPORT.md`
- `RESULTS.json`, `EVIDENCE_VERIFICATION.json`, generated patches and per-arm `RESULT.json`
- `comparison-results.zip` and its `.sha256`

The historical two-arm path instead writes:

- `results\<run-name>\deliverables\FINAL_REPORT.html` and `FINAL_REPORT.md`
- `RESULTS.csv`, `RESULTS.json`, `USAGE.json`
- `ARTIFACTS.md`, `MANIFEST.json`, `results-and-artifacts.zip` and its `.sha256`

No prior Jira issues or application results are bundled. Your new results are written under the extracted folder after a run.

## Historical two-arm PowerShell commands

For this older path, extract the ZIP to a short Windows folder such as `C:\Codex\spineharness-windows-wsl2` and open that folder in the Codex app. Run in PowerShell from the extracted folder. These commands use Ubuntu; append `-Distro Ubuntu-24.04` if that is your installed distribution name. Python, Git, uv and Codex must be installed **inside that distribution**; see [SETUP_WSL.md](SETUP_WSL.md).

```powershell
.\Run-Harness.ps1 -Action verify
.\Run-Harness.ps1 -Action doctor
# Create benchmark.json and inputs before bootstrap:
.\Run-Harness.ps1 -Action bootstrap
.\Run-Harness.ps1 -Action login -DeviceAuth
.\Run-Harness.ps1 -Action prepare
.\Run-Harness.ps1 -Action run -Approved -ApproveChecklist
```

If Windows marks the downloaded launcher as blocked, review it and use `Unblock-File .\Run-Harness.ps1`. If organizational policy blocks PowerShell scripts, ask Codex to invoke the equivalent Python commands through `wsl.exe` or use Ubuntu directly; do not change the machine's execution policy globally.

`doctor` checks the Linux tools and actually verifies sandbox confinement. `prepare` freezes requirements and tests the disposable baseline without model calls. Only `run` starts paid/model work. Use `-Approved` after baseline review and data-transfer authorization; the supplied prompt already gives that authorization. Device login displays a link and code to use in your Windows browser; if unavailable for your account, use ordinary `-Action login`.

After a closed run, regenerate all reports and the evidence ZIP without model calls:

```powershell
.\Run-Harness.ps1 -Action report
```

Keep the machine awake. A stopped or failed run is preserved; inspect its logs and choose a new run name only for an explicitly requested new attempt. There is no generic checkpoint-resume promise.

See [CONFIGURATION.md](CONFIGURATION.md) for dependency and acceptance-test settings, and [VALIDATION.md](VALIDATION.md) for what was tested. OpenAI documents [Codex with WSL2](https://learn.chatgpt.com/docs/windows/wsl) and [account authentication](https://learn.chatgpt.com/docs/auth).

## Required behavior setup for the historical two-arm path

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
