# Jira → application repository → proposed-change report

This mode reads full Jira issue keys through an MCP server and compares **spec-kit and Spine + PKG** on disposable Python repository clones. It never calls Jira write tools or pushes Git changes. Models can edit disposable copies; the original repository is not used as their working directory. The importer explicitly requests `update_history=false`.

This release has offline integration tests and a prepared Ontomesh target. It has **not** completed a live Jira/model benchmark. The current connected MCP server returned no accessible ONTM issues. An exact accessible issue key and the intended server connection are still needed to verify a real import.

## 1. Prepare the target without models

Install the pinned Spine implementation and its `dev,mcp` dependencies in a separate tool checkout. Use the reference setup instructions for that tool environment if necessary. The target application need not contain Spine's scripts or package. Do not run the old `setup.sh` with the application as SPINE_REPO.

Create a dedicated Python environment for the application's dependencies and tests, outside the original repository. Configure its executable below. Dependencies must be available in that interpreter before model execution; this command does not install them.

```bash
python3 project_benchmark.py \
  --profile profiles/ontomesh.json \
  --source "$HOME/code/ontomesh" \
  --spine-code /tmp/spine-tools/spine-code \
  --work-dir /tmp/ontomesh-benchmark-1 \
  --results "$PWD/results/ontomesh-1" \
  --python /tmp/ontomesh-python/bin/python
```

The profile pins a candidate Ontomesh commit, not an automatically approved baseline for every Jira issue. For resolved issues, choose a commit before the solution. Check that selected issues actually apply at that baseline. Copy/edit the profile for other Python repositories; non-Python execution is not supported by this adapter.

Preparation clones only committed data without hardlinks or shared object stores, removes the clone's Git remotes, and records original working-file/Git-metadata fingerprints. It preserves local uncommitted changes in the original checkout. Each workflow later receives its own clone. No model process starts during preparation.

## 2. Read Jira through MCP

Use your team's MCP server configuration, kept outside this archive. The app exposing a Jira tool does not automatically give a terminal Python process that connection. The standalone importer uses Spine's MCP transport and an explicitly supplied server configuration.

Example HTTP configuration shape (fill environment variables through your organization's normal secret management):

```json
{
  "mcpServers": {
    "jira": {
      "url": "${JIRA_MCP_URL}",
      "headers": {"Authorization": "Bearer ${JIRA_MCP_TOKEN}"},
      "allow": ["jira_get_issue"],
      "write_enabled": false
    }
  }
}
```

Using the Spine environment:

```bash
uv run --frozen --project /tmp/spine-tools/spine-code python jira_import.py \
  --keys ONTM-123,ONTM-124 \
  --jira-url https://fibonacci-solutions.atlassian.net/jira \
  --mcp-config /path/to/team-mcp.json --server jira \
  --output "$PWD/results/ontomesh-1/jira"
```

The keys above are placeholders, not retrieved or verified ONTM issues. `ONTM` alone is a project key and is rejected. If acceptance criteria are stored in a custom field, add `--acceptance-field customfield_12345` using the real field ID. Missing criteria remain missing; they are not invented. No comments, attachments, linked pages, or solution patches are followed automatically. Review omissions before considering the task representative.

Alternatively, an app operator can save `jira_get_issue` responses and use `--snapshots issue1.json issue2.json` instead of `--keys`, without a terminal MCP connection. This supports REST-shaped issue JSON and MCP structured/text envelopes.

The importer saves requirements snapshots, `scenarios.json`, `IMPORT.json` with hashes/provenance, and an initially unreviewed `REVIEW.json`. Normalization is deterministic with **zero model tokens**. Both workflows receive the same normalized requirements. This mode does not run the old separately measured, unused Spine intake step.

## 3. Review and validate without models

```bash
source results/ontomesh-1/benchmark.env
export SCENARIO_FILE="$RESULTS_DIR/jira/scenarios.json"
export TICKETS=ONTM-123,ONTM-124
uv run --frozen --project "$SPINE_CODE_DIR" python scenarios.py validate
python3 run_comparison.py --dry-run --models "$MODEL" --passes 1 --parallel 1
```

Inspect `PROJECT.json`: set `python` to the dedicated application interpreter; add issue-appropriate `checks` as argument arrays, e.g. `["{python}", "-m", "pytest", "-q", "tests/test_selected_feature.py"]`. These are trusted operator commands run only in disposable copies. Project test/check execution currently requires macOS `sandbox-exec`, with writes restricted to the disposable copy and network access denied. Execution fails closed if that sandbox or pytest is unavailable; Linux/Windows project mode is not yet supported. They execute with a reduced environment without provider/Jira/GitHub secrets. Database/service-dependent tests need a separate disposable fixture; never point them at production services.

This is **token-only mode**: held-out tests and strict create/edit fit rules are not required. Generated tests and operator checks are reported, but independent correctness is explicitly **unverified**. No project check configured means no project-quality signal, not a full-suite pass. Baseline dependencies/checks must be reviewed before a meaningful experiment.

### Required-behavior gates are a separate, independent signal

`PROJECT.json`'s `checks` (above) is this harness's own config — commands *you* choose per target, substituted into Spine's preflight seam for this benchmark run only. Spine is gaining a second, independent mechanism, native to Spine itself (SSPN-116; not yet released as of this writing — check Spine's own CHANGELOG for the version that first carries it): if the **target application** (not this harness) commits its own `.spine/required-behavior.yaml`, Spine's real `orchestrator sdlc feature` pipeline will gate on it automatically — the same way for a benchmark run as for any direct production use. Nothing in `PROJECT.json` turns this on or off; it activates purely from what the target repository itself declares.

This closes the gap ONTM-4 exposed: six generated tests passed against substituted parser/compiler implementations without the default-wiring path ever actually running. A `.spine/required-behavior.yaml` entry declares a check the model does not author and cannot edit away — e.g. "the default rule loader must invoke the configured compiler" — and Spine's native `implement → author_tests → refine` loop re-verifies it after every refinement, not just once.

What to look for in the Jira worklog Spine posts for a live run against a target with this manifest (`required_behavior`/`Outcome` are not yet surfaced in this harness's own `RESULTS.md` — that would be a separate follow-up, not covered here):

- A `required_behavior` row in the per-stage table with `0` tokens and a real, nonzero **Deterministic (s)** value — that is correct, not a bug: the check is a subprocess run, not a model call, so zero tokens does not mean it did not run.
- An **Outcome** line reading either `initial generated candidate passed with no correction needed` or `first completed autonomous workflow after N refine(s)` — the roadmap's own "distinct outcomes" framing, for the two of the three outcomes a single run can speak to. (The third, a later human-assisted continuation addressing PR review comments, deliberately does not re-verify `required_behavior` — a documented design choice, not a gap: that loop only re-runs tests and preflight.)

To exercise this in a benchmark, add `.spine/required-behavior.yaml` to the **target application's** baseline commit (not to this harness, and not to `PROJECT.json`) before preparation clones it. Example, in the target repository's own tree:

```yaml
# <target-application>/.spine/required-behavior.yaml
requirements:
  - id: default-wiring-compiles-rules
    description: Default rule loading must invoke the configured compiler
    entry_point: DefaultRuleLoader   # a symbol in the target's own graph
    command: ["python3", "check_default_wiring.py"]
    timeout: 60
    required: true
```

The manifest schema (`id`, `command`, `entry_point`, `timeout`, `required`) is documented on `Requirement` and `load_manifest()` in `ai/spine`'s `src/orchestrator/sdlc/required_behavior.py` — there is no separate schema reference yet; read the docstrings there until one exists.

After reviewing requirements and baseline, set `baseline_reviewed: true` in PROJECT.json and `reviewed: true` in the import's REVIEW.json, preserving its matching catalog hash. Changes to the catalog require another review. These reviews alone do not start model execution.

## 4. Run only when explicitly requested

Preparation exports `BENCHMARK_EXECUTE=0`. The live runner and individual arms refuse execution until it is explicitly changed. Authenticate the dedicated CODEX_LOGIN_HOME with the team's own account as in QUICKSTART. Then, only when ready:

```bash
export BENCHMARK_EXECUTE=1
python3 run_comparison.py --models "$MODEL" --passes 1 --parallel 1 --cap 100 --job-cap 20
```

The example cap suits a small selection, not all 33 reference scenarios. Caps remain API-equivalent admission estimates/stage checks, not hard limits. Checklist continuation retains the existing explicit approval policy. Project mode currently supports OpenAI/Codex arms only. MCP/Jira access is confined to the importer; benchmark model commands disable app/plugin integrations, and the project spec-kit sandbox disables network access for tool commands.

## 5. Capture evidence without applying changes

After all child processes close:

```bash
python3 report_results.py --results "$RESULTS_DIR"
```

Project mode writes `RESULTS.md` with per-issue/per-workflow proposed diffs, saved status, project check output, model IDs and reasoning evidence, token counts, and reconciled exported usage. Each attempt also has `changes.patch` and `CHANGES.md`; additions, tracked edits, staged changes, deletions, renames and binary patches are captured. Source fingerprints are compared with preparation. No patches are applied back to the original project.

Incomplete attempts remain visible. Exported failed responses count toward usage; missing exports are unknown, never assumed zero. Dollar values are **API list-price equivalents**, not subscription charges. Do not pool this token-only project mode with the original graded reference study without explaining its different intake and validation boundaries.
