# Quickstart — 33 reference scenarios, then Jira issues in your own project

Run these commands in **Bash**, from the unpacked harness. The Codex app's terminal or a normal terminal works. Every recipient uses their own repository access and ChatGPT sign-in. This archive includes no credentials, results, or Spine source checkout.

## The two-stage evaluation

1. **Default reference benchmark:** the original three scenarios plus 30 new scenarios, through both workflows on the pinned reference repository. The supplied `.env` selects all 33. No Jira connection or scenario authoring is needed. An optional one-ticket smoke pilot is available via `source profiles/pilot.env` after sourcing `.env`.
2. **Your project:** evaluate actual Jira issues against a pinned commit of **your team's repository**. Spine remains the workflow/tool being measured; your application is the code being changed. Keep these results separate from the reference pilot.

**Release boundary:** stage 1 is the validated reference path. Stage 2 now has an experimental Python adapter and read-only MCP importer: follow **[JIRA_BENCHMARK.md](JIRA_BENCHMARK.md)**. It has offline checks, with real Jira import and live model validation still pending. Replacing SPINE_REPO alone remains unsupported.

The earlier 18-run study is a reference measurement, not an expected cost, quality score, or statistically established advantage on your project. A local pilot verifies operation; project-specific results need their own evaluation.

## 1. Prerequisites and unpacking

Install Git, Bash, Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/), and the [Codex CLI](https://learn.chatgpt.com/docs/codex/cli). The measured environment used Codex CLI 0.157.0 and uv 0.8.0 on macOS. Linux/WSL is not live-tested; native PowerShell is unsupported.

```bash
unzip spec-kit-vs-spine-codex-harness-2026-09-30-v6.zip
cd spec-kit-vs-spine-codex-harness
shasum -a 256 -c SHA256SUMS  # Linux alternative: sha256sum -c SHA256SUMS
uv python install 3.12
mkdir -p "$HOME/code"
git clone https://github.com/synaptixs/spine.git "$HOME/code/spine"
cp env.example .env
# Edit SPINE_REPO in .env if you already have an authorized clone elsewhere.
source .env
```

Recipients need access to this repository, target commit, and Spine tag. If cloning fails, obtain access from the repository owner. This release supports Python create/edit scenarios on the pinned Spine target, **not arbitrary target repositories**. Installation downloads dependencies and spec-kit; model execution requires network access.

Use absolute paths. Give every experiment a new WORK_DIR and RESULTS_DIR. Keep WORK_DIR outside your home directory and the harness. `/tmp` may be cleared on reboot. Credentials belong in their separate CODEX_LOGIN_HOME, never in results or the package.

## 2. Sign in with the team's own account

```bash
umask 077
mkdir -p "$CODEX_LOGIN_HOME"
chmod 700 "$CODEX_LOGIN_HOME"
CODEX_HOME="$CODEX_LOGIN_HOME" codex -c 'cli_auth_credentials_store="file"' login
CODEX_HOME="$CODEX_LOGIN_HOME" codex login status
```

Choose **Sign in with ChatGPT**. On a headless host, use `login --device-auth` if allowed by the organization. Follow managed authentication requirements if they prohibit file storage. Never copy another person's auth cache. [Official authentication guidance](https://learn.chatgpt.com/docs/auth).

The account must support the exact MODEL in `.env`. If another model is required, label it as a separate experiment and verify its published rates in `codex_usage.py`. The harness cannot grant model access. Default subscription mode clears API credential variables.

## 3. Setup and checks — no model calls

```bash
bash setup.sh
uv run --frozen --project "$WORK_DIR/spine-code" python -m unittest -v \
  test_codex_backend test_report_usage test_scenarios
uv run --frozen --project "$WORK_DIR/spine-code" python scenarios.py list
uv run --frozen --project "$WORK_DIR/spine-code" python scenarios.py validate
python3 run_comparison.py --dry-run --models "$MODEL" --passes 1 --parallel 1
```

Setup should end with `== ready`. It creates two pinned detached worktrees and installs locked dependencies. Validation checks selected IDs, required edit targets, held-out syntax, and agreement between the target and Spine catalogs. It does not prove that a custom judge is correct or that the account has model access. Review new judges before spending model capacity.

## 4. Default 33-scenario run (start explicitly)

After sourcing the supplied `.env`, all **33 scenarios** are selected: the original severity summary, ledger Markdown, and drift Markdown tasks, plus [30 additional requirements](catalog/INDEX.md). The additions comprise **15 edits and 15 new modules**, with 111 held-out test cases. One pass schedules **66 ticket-arm runs plus 33 separate intake measurements**. Three passes schedule 198 ticket-arm runs plus 99 intakes. These run on the reference repository even if the later evaluation will use your application.

Nothing starts automatically when you unpack or source configuration. Setup, validation, and `--dry-run` make no model calls. The following command starts the live benchmark; run it only when ready:

```bash
python3 run_comparison.py --models "$MODEL" --passes 1 --parallel 1 \
  --cap 600 --job-cap 20
```

For an optional smaller pilot instead, use fresh work/results directories, `source profiles/pilot.env` after `.env`, validate again, and run the same command with `--cap 25`. Re-source `.env` to select all 33 again.

The runner saves `EXPERIMENT.json` before model execution, including task/judge fingerprints, selected scenarios, versions, and policy. Both workflows run serially in subscription mode. Watch `$RESULTS_DIR/$MODEL/logs/`; a stage's log can remain unchanged while its model process runs.

**Checklist policy:** spec-kit can pause before implementation because reviewer checklist items are unchecked. Inspect its output. If your operator approves proceeding, either use `--approve-checklist` on a **fresh** batch, or recover a saved checklist pause after its original process exits:

```bash
uv run --frozen --project "$WORK_DIR/spine-code" python speckit_codex.py \
  "$MODEL" NEW-SEVSUMMARY-1 1 --cap 20 --resume-checklist --approve-checklist
```

Recovery preserves earlier usage and does not mark reviewer boxes. Both live checklist recovery and a completed 18-run stock study have been exercised. Organizational/app approvals remain in force.

`--cap` is a conservative pass-admission estimate; `--job-cap` checks spec-kit cost between stages. Neither is a hard spending limit. Costs in subscription mode are **API list-price equivalents, not charges**. The default fallback admission reserve is $16 per spec-kit ticket per model plus $1 per Spine pass; larger catalogs can require a larger cap even when observed cost is lower.

When the benchmark's child processes exit, run `python3 report_results.py --results "$RESULTS_DIR"` and review `summary.md`, usage completeness, and functional results. Resolve failures before moving to your own project. Keep the reference output unchanged; use fresh work/results directories for the next stage.

## 5. Actual Jira issues in your team's repository

For example, a team owns `orders-service`, a Python application, and wants to evaluate Jira issue **ORD-142: reject invalid page sizes**. This is a fictional mapping example for that application, not a runnable stock Spine scenario. For automatic import by Jira key, use [JIRA_BENCHMARK.md](JIRA_BENCHMARK.md). The manual mapping below remains useful for reviewing the resulting requirements.

### Freeze the issue and baseline

Choose the full Git commit before the fix, at which the issue is reproducible and dependencies install. For a resolved issue, exclude the solution commit, patch, and resolution comments from model inputs. Capture the issue's requirements as they were before implementation. Record the source Jira URL, export date, repository identity, baseline SHA, and adapter version in a separate provenance file; the scenario schema does not accept those extra fields.

If several issues need different baseline commits, use separate experiments. In each pair, spec-kit and Spine must receive the same issue text and start from the same clean commit. Both workflows should use the same model and reasoning settings.

| Jira / project information | Catalog field |
|---|---|
| Issue key (`ORD-142`) | `key` |
| Summary | `spec.title` |
| Description and expected behavior | `spec.summary` |
| Relevant API, code paths, and constraints | `spec.technical_notes` |
| Acceptance criteria | `spec.acceptance_criteria` |
| Existing files that must change, reviewed by the team | `must_edit` for an `edit` task |
| Independently authored evaluation tests | `held_out_tests`; these do not come automatically from Jira |

Create this layout **outside the target repo and generated worktrees**:

```text
team-jira/
  scenarios.json
  provenance.md
  heldout/
    test_ord_142.py
```

Example `team-jira/scenarios.json`:

```json
{
  "schema_version": 1,
  "scenarios": [
    {
      "key": "ORD-142",
      "kind": "edit",
      "must_edit": ["src/orders/pagination.py"],
      "spec": {
        "title": "Reject invalid page sizes",
        "summary": "list_orders currently accepts page sizes outside the supported range. Centralize validation in the existing validate_page_size function.",
        "technical_notes": "In src/orders/pagination.py, validate_page_size(value: int) -> int must return valid values unchanged and raise ValueError for out-of-range integers. list_orders already calls this function. Preserve its public signature. Input type coercion is outside this issue's scope.",
        "acceptance_criteria": [
          "Integer page sizes from 1 through 100 inclusive are returned unchanged.",
          "Zero, negative integers, and integers above 100 raise ValueError.",
          "Existing callers and regression tests continue to work."
        ]
      },
      "held_out_tests": ["heldout/test_ord_142.py"]
    }
  ]
}
```

Example `team-jira/heldout/test_ord_142.py`:

```python
import pytest
from orders.pagination import validate_page_size

@pytest.mark.parametrize("value", [1, 2, 50, 99, 100])
def test_accepts_supported_page_sizes(value):
    assert validate_page_size(value) == value

@pytest.mark.parametrize("value", [-100, -1, 0, 101, 1000])
def test_rejects_unsupported_page_sizes(value):
    with pytest.raises(ValueError):
        validate_page_size(value)
```

Replace the example API and paths with your application's actual contract. Confirm that the tests fail on the baseline because of the bug, pass on a known-correct implementation, and reject a plausible incorrect fix. An import error alone is not evidence of a reproduced bug. Run existing regression tests as well; these example assertions do not cover the entire service.

You can check catalog syntax and test-file presence before an adapter exists, with no repository imports or model calls:

```bash
python3 - <<'PYTHON'
from pathlib import Path
from scenario_catalog import load_catalog
rows, metadata = load_catalog(Path("team-jira/scenarios.json"))
print("Prepared issues:", ", ".join(row["key"] for row in rows))
print("Catalog fingerprint:", metadata["catalog_sha256"])
PYTHON
```

This check does not execute the tests or make the application a supported target.

### Repository adapter checklist

The experimental project mode now separates clones/imports/checks as described in JIRA_BENCHMARK.md. This checklist explains the couplings it replaces and what each team must validate:

| Adapter responsibility | Required behavior / current coupling |
|---|---|
| Separate tool and application checkouts | Keep the pinned Spine implementation separate from the team's target repo. `setup.sh` currently creates both worktrees from `SPINE_REPO`; spec-kit also creates run worktrees from it. Both arms must instead create isolated application worktrees at the chosen baseline. |
| Target dependencies | Install the application's locked dependencies and use its runtime for tests and static checks. Current setup and runner commands assume Spine's Python/uv layout. |
| Harness imports and graph | Load benchmark helpers from the tool checkout, not from the application. `harness_config.use_tree`, `scenarios.py`, and spec-kit imports currently expect `scripts/codegen_benchmark.py` and `orchestrator` in the target. Verify Spine's package/graph discovery on the actual application. |
| Shared task and judge | Feed the identical frozen Jira spec and held-out judge to both arms and matching intake. Keep judges and reference solutions outside model-visible task text and the target graph. |
| Project grading | Use the team's tests, lint/type checks, and CI gates. Replace the Spine-specific `scripts/state-numbers.py --check` gate. Review the inherited create/edit fit rules for legitimate multi-file, configuration, or migration changes. |
| Evidence and reports | Record application identity, full baseline SHA, adapter revision, commands, task/judge hashes, failures, and complete per-response usage. Extend the generic report if grading fields change; preserve matching by issue/pass/model. |
| Required-behavior gates (optional, target-declared) | Independent of this harness's own `checks` config — if the target application itself commits `.spine/required-behavior.yaml`, Spine's native pipeline gates on it automatically, no adapter change needed. See **[JIRA_BENCHMARK.md](JIRA_BENCHMARK.md)**, "Required-behavior gates are a separate, independent signal." |

There is no supported `TARGET_REPO` switch in this release. Do not point `SPINE_REPO` at `orders-service`, copy Spine benchmark files into it, or treat a successful catalog syntax check as adapter validation. Non-Python projects also need language-specific discovery, execution, and grading.

For the experimental adapter, follow JIRA_BENCHMARK.md to select the prepared catalog with `SCENARIO_FILE` and `TICKETS=ORD-142`, using fresh work/results directories. First run one paired project pilot and inspect code, tests, and accounting. Then freeze the adapter and expand to different Jira problems and repeated passes. The separate guide supplies setup/run instructions; the stock commands above only support the reference target.

Keep the reference pilot and application study separate in reports. Use distinct issues as the problem sample; repeats of one issue measure variability, not additional independent problems. Group analysis by repository when several repositories are involved.

## 6. Optional: add scenarios on the reference repository

Full instructions and schema: **[SCENARIOS.md](SCENARIOS.md)**. The two included examples exercise an edit to an existing module and creation of a new module.

```bash
# Copy the sample catalog and its separate held-out tests.
cp -R examples team-scenarios
# Edit team-scenarios/scenarios.json and team-scenarios/heldout/test_*.py.
# Keep this directory outside WORK_DIR and SPINE_REPO.
```

For a new experiment, edit `.env` to use **fresh** WORK_DIR and RESULTS_DIR and add:

```bash
export SCENARIO_FILE="$PWD/team-scenarios/scenarios.json"
export TICKETS=CUSTOM-EDIT-RANGE-1,CUSTOM-NEW-HISTOGRAM-1
# You may mix built-in and custom IDs in the same comma-separated list.
```

Then reload and validate:

```bash
source .env
bash setup.sh
uv run --frozen --project "$WORK_DIR/spine-code" python scenarios.py list
uv run --frozen --project "$WORK_DIR/spine-code" python scenarios.py validate
python3 run_comparison.py --dry-run --models "$MODEL" --passes 3 --parallel 1
```

After reviewing the catalog, budget, and checklist policy, run:

```bash
python3 run_comparison.py --models "$MODEL" --passes 3 --parallel 1 \
  --cap 200 --job-cap 20 --approve-checklist
```

This two-scenario example schedules **12 ticket-arm runs**, plus six separate intake measurements. In general: scenarios × repeats × workflows × models. Do not edit scenario definitions or tests during a batch. Freeze the catalog with your experiment records; changing either changes its fingerprint.

The bundled catalog is loaded when SCENARIO_FILE is unset; it adds 30 tasks to the ten built-ins. `scenarios.py list` therefore lists **40 available IDs**, while the default selects **33**. An explicit custom SCENARIO_FILE replaces the bundled extension, so set TICKETS to IDs available in that custom catalog or the ten built-ins. The built-ins comprise: five create and five edit tasks. A six-scenario example is:

```bash
export TICKETS=NEW-SEVSUMMARY-1,NEW-LEDGERMD-1,NEW-DRIFTMD-1,EDIT-STATS-1,EDIT-LEDGER-1,EDIT-BUDGET-1
```

Use fresh directories and repeat setup/validation for that experiment. Three passes across two workflows produce **36 ticket-arm runs**; the fallback reserve is $97 per pass for one model, so choose a suitable admission cap rather than assuming the pilot cap works. For the default 33-task selection the fallback reserve is $529 per pass; `--cap 600` admits one pass, while `--cap 200` would not. These are admission reserves, not cost predictions or hard limits.

## 7. Report and hand back results

Only after all child processes have exited:

```bash
python3 report_results.py --results "$RESULTS_DIR"
```

Read `summary.md` and `recorded-usage.json`. The report begins with the models used for each workflow and separate intake, reasoning settings, saved measurement counts, and model IDs found in exported response records. Missing metadata is labeled unknown; configured values are identified as such. The report supports arbitrary catalog sizes, matches intake by ticket/pass, and compares scenario means rather than treating repeats as independent problems. It defers inference when planned paired measurements are incomplete. No quality-equivalence claim follows from equal pass counts. The old `summarize.py` is legacy exploratory analysis; use `report_results.py` for new experiments.

Return `EXPERIMENT.json`, your frozen scenario catalog and test hashes, `summary.md`, `recorded-usage.json`, per-run `summary.json` files, intake `pass*.json`, and any failure records. Review source code and task context before sharing raw transcripts or generated code. Never include `.env`, auth.json, CODEX_LOGIN_HOME, or the entire WORK_DIR. Missing exported usage means unknown usage, not zero.

## 8. Failures and interpretation

| Symptom | Action |
|---|---|
| Unknown or duplicate ID | Use `scenarios.py list`; IDs are case-sensitive and must be unique. |
| Custom tests not found / syntax error | Fix paths relative to the catalog and validate again before a fresh run. |
| Target and Spine fingerprints differ | Resolve the task/judge mismatch; do not compare mismatched tasks. |
| Catalog changed during a run | Stop and preserve that experiment; the report rejects mixed fingerprints. |
| Model unavailable, capacity error, quota stop | Preserve failed output. Wait for availability or start a separately labeled experiment on another model. |
| Existing output / JOB_FAILED | Do not overwrite it. Inspect the failure and use fresh experiment directories for a new attempt. |
| Checklist pause | Use the documented approved checklist recovery after the job exits. |
| Repository-count gate failure | Record it separately; it is not the full test suite and does not alone establish functional failure. |
| Missing response records | Treat token accounting as incomplete and check CLI compatibility. |

The batch runner is not a general resume scheduler. `--resume-capacity` is retained for a manually captured, verified capacity checkpoint; it does not create such a checkpoint or provide automatic recovery. The completed study's one-off recovery driver is not shipped. New JSON scenarios and edit-file detection have offline integration checks, not a new paid model benchmark. See METHODOLOGY.md for study-design limits.

## Expanded-catalog validation status

The 30 additions have been checked offline against the pinned model types, absent implementations, temporary reference implementations, and deliberately incorrect implementations. They have not been benchmarked with live models. Their variety does not guarantee statistical independence or adequate power: all tasks share one repository and several task families. Report per-family outcomes and qualify cross-project conclusions.
