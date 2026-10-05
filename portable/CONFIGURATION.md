# Configuration for another repository and Jira issues

Copy `benchmark.example.json` to `benchmark.json`. Paths may be absolute, start with `~`, or be relative to the config file. Do not place credentials in it.

| Setting | Meaning |
|---|---|
| `name` | Unique experiment name. Existing result/work directories are never overwritten. |
| `source_repo` | Local application checkout. Only committed content at the selected baseline is cloned. |
| `repository_url` | Repository identification for reporting; no embedded credentials. |
| `baseline` | Commit/tag or HEAD, resolved once during preparation. Pick a commit where the issue is not already solved and prerequisites are available. |
| `jira_url`, `issues` | Your Jira site and full issue keys. |
| `snapshots` | One saved Jira REST-shaped or supported MCP response JSON per issue, obtained by read-only tools. |
| `requirements_files` | Repository-relative requirements files installed in a dedicated test environment, e.g. `["requirements.txt", "requirements-test.txt"]`. Use `[]` if none. |
| `extra_test_packages` | Additional test dependency package specs, e.g. `["pytest-asyncio"]`. Prefer your lockfiles. |
| `install_project` | If true, install the disposable baseline with `uv pip install -e`. |
| `application_python` | Optional existing dedicated application interpreter. If provided, automatic app-environment installation is skipped. Its dependencies must already be complete. Do not use an interpreter with production secrets. |
| `source_paths` | Import roots relative to each disposable checkout, usually `[".", "src"]`. |
| `checks` | Required regression commands as argument arrays. `{python}` is replaced with the application interpreter. No shell strings. |
| `acceptance_tests` | Optional map from issue key to external pytest files, frozen before the run and evaluated after generation on both arms. |
| `passes` | Repeats per issue per workflow. Start with 1. |
| `model`, `reasoning_effort` | Default gpt-6-sol/high. A different model needs account access and verified rates in codex_usage.py. Do not silently substitute models. |
| `completion_timeout_seconds` | Spine completion timeout, default 2700. Previous 300-second deadlines caused missing-usage failures. |
| `cap`, `job_cap` | API-equivalent admission/stage budgets, not hard spending ceilings and not subscription charges. |
| `tools_dir`, `login_home` | Default `.local/spine-tools` and `~/.codex-spineharness`. Login never goes inside work/results. |
| `work_dir`, `results_dir` | Defaults to a temporary macOS work root and `results/<name>` alongside the config. Keep them separate from each other and the original checkout. |

Example frozen acceptance configuration:

```json
"acceptance_tests": {
  "TEAM-123": ["acceptance/test_team_123.py"]
}
```

These tests should exercise real behavior with offline fixtures and exist before the model run. They are held outside the model's disposable checkout. Regression checks are run before measurement and must pass at baseline. Acceptance checks may intentionally fail at baseline because they describe the missing feature. A passing selected suite does not establish complete Jira acceptance. If its failures are later supplied to a model, label that later work post-audit continuation and retain both token costs.

If using a terminal MCP connection instead of app-saved snapshots, omit snapshots and set `mcp_config` to your team's external MCP configuration and `mcp_server` to its server name. The importer uses Spine's MCP client with only `jira_get_issue`, zero comments and `update_history=false`. The Codex app's connected Jira tool is not automatically inherited by a Python subprocess. Never bundle the MCP config or Jira token.

Saved snapshots can contain Jira rich-text (ADF) descriptions. Add `acceptance_field: "customfield_12345"` if your Jira stores criteria in a separate field. Comments, attachments, linked pages and solution patches are not fetched automatically; review whether their omission makes the issue incomplete. The selected snapshots must match the configured keys exactly.

The two workflows receive the same requirements and independent clones of the same baseline. A multi-issue run does not carry one issue's implementation into another. Benchmark related prerequisite issues together only with an explicitly prepared common baseline and disclosed scope.

The primary path in this release is `benchmark.py`. Legacy modules and advanced reference-scenario utilities remain included for reproducibility; do not use the old reference-only `setup.sh` against your application repository.
