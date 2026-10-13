# Quickstart — 33 reference scenarios across four workflows

The default reference study runs each of the 33 scenarios through **Spec Kit, standalone OpenSpec, Spine + integrated OpenSpec + PKG, and Spine + PKG**. The v19 pins are **Spec Kit `v1.0.11`**, **OpenSpec CLI `1.14.1`** for its standalone arm, and **Spine `v3.57.1`** for both PKG arms. PKG and Spine's OpenSpec integration ship with Spine rather than carrying separate pins. See the [four-arm tool table](MATRIX_QUICKSTART.md#tools-and-versions-in-v19).

Graphify and codebase memory are candidates for future adapters; neither is part of this release or its 33-scenario results. For Jira, SWE-bench, or a user-supplied framework on a matched task, use [FRAMEWORK_MATRIX.md](FRAMEWORK_MATRIX.md). `run_comparison.py` remains the historical two-arm reproduction path.

Run these commands in **Bash**, from the unpacked harness. The Codex app's terminal or a normal terminal works. Every recipient uses their own repository access and ChatGPT sign-in. This archive includes no credentials or results; it includes a Git bundle for the pinned four-arm Spine tools revision, but no installed environment or target application checkout.

## The two-stage evaluation

1. **Default reference benchmark:** the original three scenarios plus 30 new scenarios, through all four workflows on the pinned reference repository. The supplied `env.example` selects all 33. No Jira connection or scenario authoring is needed. An optional one-ticket smoke pilot is available via `source profiles/pilot.env` after sourcing the environment.
2. **Your project:** evaluate actual Jira issues against a pinned commit of **your team's repository**. Spine remains the workflow/tool being measured; your application is the code being changed. Keep these results separate from the reference pilot.

**Release boundary:** the historical two-arm reference path has completed runs. The four-arm reference matrix has an offline plan and configuration check; a full 132-measurement model run has not yet been made. For Jira issues in an external application, use [MATRIX_QUICKSTART.md](MATRIX_QUICKSTART.md) with a saved read-only issue snapshot. Replacing SPINE_REPO alone does not change the target application.

The earlier 18-run study is a reference measurement, not an expected cost, quality score, or statistically established advantage on your project. A local pilot verifies operation; project-specific results need their own evaluation.

## 1. Prerequisites and unpacking

Install Git, Bash, Python 3.12, Node/npm, [uv](https://docs.astral.sh/uv/getting-started/installation/), the [Codex CLI](https://learn.chatgpt.com/docs/codex/cli), and the official OpenSpec CLI (`npm install -g @fission-ai/openspec@1.14.1`). The measured environment used Codex CLI 0.157.0 and uv 0.8.0 on macOS. Linux/WSL is not live-tested; native PowerShell is unsupported. For a **one-repository, one-issue four-arm pilot**, use [MATRIX_QUICKSTART.md](MATRIX_QUICKSTART.md) first.

```bash
unzip spineharness-macos-2026-10-13-v19.zip
cd spineharness-macos
shasum -a 256 -c SHA256SUMS  # Linux alternative: sha256sum -c SHA256SUMS
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
uv python install 3.12
mkdir -p "$HOME/code"
git clone -q -b v3.57.1 release_assets/spine-tools-v3.57.1.bundle "$HOME/code/spine"
git -C "$HOME/code/spine" rev-parse HEAD
cp env.example .env
# Edit SPINE_REPO in .env if you already have an authorized clone elsewhere.
source .env
```

The printed Spine commit must equal `a8952c1a14fc31601fb5721b77b61e36003287e3`. The bundle contains the target commit and release tag; no separate Spine GitHub clone is required. This reference study supports Python create/edit scenarios on the pinned Spine target, **not arbitrary target repositories**. Installation downloads dependencies and spec-kit; model execution requires network access.

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
PYTHONPATH="$PWD/src:$WORK_DIR/spine-code/src" uv run --frozen --project "$WORK_DIR/spine-code" python -m unittest -v \
  tests.test_codex_backend tests.test_report_usage tests.test_scenarios
uv run --frozen --project "$WORK_DIR/spine-code" python -m spineharness.scenarios list
uv run --frozen --project "$WORK_DIR/spine-code" python -m spineharness.scenarios validate
python3 -m spineharness.reference_matrix dry-run --model "$MODEL" --passes 1
```

Setup should end with `== ready`. It creates two pinned detached worktrees and installs locked dependencies. Validation checks selected IDs, required edit targets, held-out syntax, and agreement between the target and Spine catalogs. It does not prove that a custom judge is correct or that the account has model access. Review new judges before spending model capacity.

## 4. Default 33-scenario run (start explicitly)

After sourcing the supplied environment, all **33 scenarios** are selected: the original severity summary, ledger Markdown, and drift Markdown tasks, plus [30 additional requirements](../catalog/INDEX.md). The additions comprise **15 edits and 15 new modules**, with 111 held-out test cases. One pass schedules **132 ticket-arm measurements** (33 × 4); three passes schedule 396. Native Spine intake is included in each relevant Spine arm's measured workflow, rather than counted as a separate arm. All four arms receive the same task and source baseline; held-out tests run only after each arm closes.

Nothing starts automatically when you unpack or source configuration. Setup, validation, and `--dry-run` make no model calls. The following command starts the live benchmark; run it only when ready:

```bash
python3 -m spineharness.reference_matrix prepare --model "$MODEL" --passes 1
# Review reference-matrix/MATRIX_PLAN.json and the prepared baselines.
python3 -m spineharness.reference_matrix run --approved
```

For an optional smaller pilot instead, use fresh work/results directories, `source profiles/pilot.env` after the environment, validate again, and run the same prepare/run commands. Re-source `env.example` to select all 33 again. The matrix deliberately has no budget-cap estimate; monitor your account limits and run a pilot before the full study.

The runner freezes `MATRIX_PLAN.json`, per-scenario task/check inputs, source fingerprints, and framework versions before model execution. It runs one scenario/arm at a time and preserves each closed result under `$RESULTS_DIR/reference-matrix/runs/`. The aggregate report is `$RESULTS_DIR/reference-matrix/study/MATRIX_STUDY_REPORT.md`. Watch each arm's logs and `RESULT.json`; a log can remain unchanged while its model process runs. Use a Spine pin containing the OpenSpec intent-extraction fix described in [FRAMEWORK_MATRIX.md](FRAMEWORK_MATRIX.md); unpatched 3.56.0 can reject a valid draft at its clarity gate.

**Checklist policy:** the reference matrix config records approval for routine spec-kit checklist continuation. The historical two-arm path supports manual recovery of a saved checklist pause after its original process exits:

```bash
uv run --frozen --project "$WORK_DIR/spine-code" python -m spineharness.speckit_codex \
  "$MODEL" NEW-SEVSUMMARY-1 1 --cap 20 --resume-checklist --approve-checklist
```

Recovery preserves earlier usage and does not mark reviewer boxes. Both live checklist recovery and a completed 18-run stock study have been exercised. Organizational/app approvals remain in force.

Costs in subscription mode are **API list-price equivalents, not charges**. The matrix preserves unknown usage as unknown and reports stage consumption separately. It does not impose a spending cap.

When the benchmark closes, review `MATRIX_STUDY_REPORT.md`, individual `COMPARISON_REPORT.md` files, usage completeness, code patches, and functional results. `python3 -m spineharness.reference_matrix report` rebuilds the study only if no study output exists. Keep the reference output unchanged; use fresh work/results directories for the next stage.

## 5. Actual Jira issues in your team's repository

For example, a team owns `orders-service`, a Python application, and wants to evaluate Jira issue **ORD-142: reject invalid page sizes**. This is a fictional mapping example for that application, not a runnable stock Spine scenario. For a saved Jira issue snapshot in the four-arm runner, use [MATRIX_QUICKSTART.md](MATRIX_QUICKSTART.md). The manual mapping below remains useful for reviewing the resulting requirements.

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
| Required-behavior gates (optional, target-declared) | Spine 3.57.1's production feature pipeline uses a target `.spine/required-behavior.yaml`. Jira/project mode now invokes that production loop. Supply real public checks in the prepared baseline; its failures drive bounded native refinement. See [FRAMEWORK_MATRIX.md](FRAMEWORK_MATRIX.md) for selected correctness and independent acceptance checks. |

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
uv run --frozen --project "$WORK_DIR/spine-code" python -m spineharness.scenarios list
uv run --frozen --project "$WORK_DIR/spine-code" python -m spineharness.scenarios validate
python3 -m spineharness.reference_matrix dry-run --model "$MODEL" --passes 3
```

After reviewing the catalog, checks, and model capacity, run:

```bash
python3 -m spineharness.reference_matrix prepare --model "$MODEL" --passes 3
python3 -m spineharness.reference_matrix run --approved
```

This two-scenario example schedules **24 ticket-arm measurements** (2 × 3 × 4). In general: scenarios × passes × frameworks. Do not edit scenario definitions or tests during a batch. The prepared matrix freezes their hashes and refuses changed acceptance inputs.

The bundled catalog is loaded when SCENARIO_FILE is unset; it adds 30 tasks to the ten built-ins. `scenarios.py list` therefore lists **40 available IDs**, while the default selects **33**. An explicit custom SCENARIO_FILE replaces the bundled extension, so set TICKETS to IDs available in that custom catalog or the ten built-ins. The built-ins comprise: five create and five edit tasks. A six-scenario example is:

```bash
export TICKETS=NEW-SEVSUMMARY-1,NEW-LEDGERMD-1,NEW-DRIFTMD-1,EDIT-STATS-1,EDIT-LEDGER-1,EDIT-BUDGET-1
```

Use fresh directories and repeat setup/validation for that experiment. Three passes over six scenarios and four frameworks produce **72 ticket-arm measurements**. The default 33-scenario selection produces **396** over three passes. This is a substantial model workload; start with one scenario and one pass to verify the environment.

## 7. Report and hand back results

The four-arm batch writes the aggregate study after all selected scenarios close. If every scenario is closed but the aggregate was never generated, run:

```bash
python3 -m spineharness.reference_matrix report
```

Read `reference-matrix/study/MATRIX_STUDY_REPORT.md` and each task's `COMPARISON_REPORT.md`, `RESULTS.json`, stage usage, patches, and acceptance output. The study compares matched task/pass pairs and collapses repeats within each task for the sign test. It distinguishes workflow completion from acceptance and marks missing usage unknown. A full 33-scenario set is still one reference repository, not a random sample of projects; interpret statistical tests accordingly. For the historical two-arm runner, use `report_results.py` and keep its outputs separate.

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
