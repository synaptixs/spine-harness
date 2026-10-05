# Linux prerequisites for the Windows package

Use the same WSL2 Ubuntu distribution for every command. These are setup commands for Codex to run; the user's interaction should normally be limited to required administrator/sign-in prompts.

From PowerShell, enter Ubuntu:

```powershell
wsl --distribution Ubuntu
```

Inside Ubuntu, install system dependencies:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl ca-certificates bubblewrap build-essential
```

Install uv in a dedicated Python environment and expose both commands without replacing system Python:

```bash
python3 -m venv "$HOME/.local/share/spineharness/bootstrap-venv"
"$HOME/.local/share/spineharness/bootstrap-venv/bin/python" -m pip install uv
mkdir -p "$HOME/.local/bin"
# Skip an existing uv/uvx command; do not replace another installation.
test -e "$HOME/.local/bin/uv" || ln -s "$HOME/.local/share/spineharness/bootstrap-venv/bin/uv" "$HOME/.local/bin/uv"
test -e "$HOME/.local/bin/uvx" || ln -s "$HOME/.local/share/spineharness/bootstrap-venv/bin/uvx" "$HOME/.local/bin/uvx"
export PATH="$HOME/.local/bin:$PATH"
```

Install Linux Codex using the [official CLI installer](https://learn.chatgpt.com/docs/codex/cli) if it is missing. The following saves the installer for inspection before executing it:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh -o /tmp/spineharness-install-codex.sh
# Inspect the downloaded installer, then:
sh /tmp/spineharness-install-codex.sh
codex --version
uv --version
```

The harness bootstrap downloads Python 3.12 as needed and installs the pinned Spine dependencies. Tools live in the Linux filesystem under `~/.local/share/spineharness/`; sign-in stays in Linux `~/.codex-spineharness`. Neither is exported in results. Never copy Windows/macOS login files into this package.

Use Linux paths in benchmark.json. For example, `C:\code\my-app` becomes `/mnt/c/code/my-app`; a Linux clone can use `/home/yourname/code/my-app` or `~/code/my-app`. `~` always means the Ubuntu user's home. Windows paths in configuration are rejected instead of silently treated as relative filenames. For performance, a Linux source clone is preferable. Tool and application virtual environments must be Linux environments, not Windows `.venv\Scripts\python.exe` installations.

The PowerShell launcher adds `~/.local/bin` and `~/.npm-global/bin` to PATH. If Codex is installed somewhere else, expose it under `~/.local/bin` or the inherited WSL PATH. The launcher does not source shell profiles. `-SpineSource` accepts an authorized Git URL or a Linux path, not a Windows drive path.

The doctor command must pass before a paid run. It checks that a disposable checkout is writable, files outside it and symlink escapes are blocked, and a listener in the host network is unreachable from the sandbox. Namespace or AppArmor policy failures stop setup. Use WSL2, update WSL if needed, and have your administrator resolve namespace policy; never remove bubblewrap or substitute unsandboxed project checks.

Equivalent commands from Ubuntu, after changing into the extracted package (for example `/mnt/c/Codex/spineharness-windows-wsl2`):

```bash
python3 verify_package.py
python3 benchmark.py doctor
python3 benchmark.py bootstrap
python3 benchmark.py login --device-auth
python3 benchmark.py prepare
python3 benchmark.py run --approved --approve-checklist
python3 benchmark.py report
```

Live model access, package downloads, and Jira authentication depend on the recipient's environment. The app's connected Jira tool is not inherited by the Python process: save read-tool responses in `inputs/`, or configure the supported terminal MCP importer.
