# Quick start — Windows with WSL2

This archive runs the harness in **WSL2 Ubuntu**, controlled from the **Windows Codex app**. It supports Python applications. Native Windows Python and WSL1 are not supported by this harness.

## 1. Unzip and open in Codex

Extract to a short local folder such as `C:\Codex\spineharness-windows-wsl2`. Open that folder as a project in the Codex app.

If WSL2 is not installed, run this once in Administrator PowerShell, restart if requested, then open Ubuntu and finish creating your Linux username:

```powershell
wsl --install -d Ubuntu
```

Check `wsl --list --verbose` shows version **2** for Ubuntu. Existing WSL2 users can skip installation. [Microsoft's WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install) explains these steps.

## 2. Paste this into Codex

Replace the bracketed values:

> Read AGENTS.md and QUICKSTART.md. Set up and run this Windows/WSL2 harness using Ubuntu, my Python repository at **[repository path]**, baseline **[commit/tag or HEAD]**, Jira site **[https://team.atlassian.net]**, and issues **[TEAM-123, TEAM-456]**. Install missing Linux prerequisites using SETUP_WSL.md, save selected Jira requirements with connected read-only tools, and create benchmark.json with WSL paths. Use Run-Harness.ps1 from Windows. Configure the repository's actual dependencies and offline regression checks. Use my own ChatGPT sign-in, gpt-6-sol/high, one pass per workflow, and a fresh run name. I authorize sending those selected Jira requirements and relevant disposable repository code to OpenAI/ChatGPT for this benchmark and proceeding through routine spec-kit checklist gates while recording unchecked items. Verify sandbox isolation and the common baseline before running. Run through completion and generate the final report, results and evidence ZIP, including partial results on failure. Do not change my source checkout or Jira, repair measured output manually, or start a new full attempt automatically.

Codex handles setup and execution. You may need to complete the Linux administrator password prompt, sign in to ChatGPT, and allow commands through the app's normal permissions. Your own authorized access to Spine, the application repository and the selected Jira issues is required. Start with one or two independent issues.

## 3. Open your results

By default the outputs are in the extracted Windows folder:

- `results\<run-name>\deliverables\FINAL_REPORT.html` and `FINAL_REPORT.md`
- `RESULTS.csv`, `RESULTS.json`, `USAGE.json`
- `ARTIFACTS.md`, `MANIFEST.json`, `results-and-artifacts.zip` and its `.sha256`

The completed ONTM-4 final report and evidence are included under `reference\results\`. That historical study ran on macOS; it is not proof of Windows execution or an expected result for your new issues.

## Commands Codex will use

Run in PowerShell from the extracted folder. These commands use Ubuntu; append `-Distro Ubuntu-24.04` if that is your installed distribution name. Python, Git, uv and Codex must be installed **inside that distribution**; see [SETUP_WSL.md](SETUP_WSL.md).

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
