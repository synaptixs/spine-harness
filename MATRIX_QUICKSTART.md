# Start here: one repository, one issue, four workflows

This is the recommended **qualification pilot** for the framework matrix. It runs one issue once through spec-kit, OpenSpec, Spine + PKG + OpenSpec, and Spine + PKG in separate disposable clones. It does **not** start the 33-scenario reference study. The original repository and issue tracker are read-only; generated code stays in the disposable work directory and result patches.

The October 8 public Spine #456 pilot exercised all four arms and produced a complete four-row report. Three arms passed its independent feature check; Spine + PKG + OpenSpec stopped at an unresolved scope question before implementation. The updated adapter records a frozen operator answer or named deferral through Spine's native clarity API. A subsequent isolated #456 run reached implementation and passed its selected feature check and 63 regression tests. Spine's native judge still rejected that generated implementation because it did not prove preservation of all genuine imported-library members. The integration path runs; this particular generated patch did **not** pass native validation. A model, dependency, or acceptance failure is a recorded result, not permission to silently repair or rerun.

## 1. Unpack and verify on macOS

Install Git, Python 3.12, [uv](https://docs.astral.sh/uv/getting-started/installation/), Node/npm, and the Codex CLI. Use a ChatGPT login with access to the configured model. The pilot used OpenSpec **1.14.1**. From the extracted archive:

```bash
cd spineharness-macos
shasum -a 256 -c SHA256SUMS
npm install -g @fission-ai/openspec@1.14.1
codex --version
openspec --version
uvx --version
```

The release includes `release_assets/spine-tools-v3.57.1.bundle`, a Git bundle containing the published Spine `v3.57.1` tools revision `a8952c1a14fc31601fb5721b77b61e36003287e3`. It makes the exact tools revision available without separate GitHub access. It is a **tools** checkout; `source_repo` below is the separate application being tested. The public #456 pilot above used a pre-release ancestor and remains historical evidence, not a 3.57.1 measurement.

```bash
mkdir -p .local
git clone -q -b v3.57.1 \
  release_assets/spine-tools-v3.57.1.bundle .local/spine-tools-v3.57.1
git -C .local/spine-tools-v3.57.1 rev-parse HEAD
(cd .local/spine-tools-v3.57.1 && uv sync --frozen --extra dev --extra mcp \
  --extra typescript --extra java --extra csharp --extra c --extra cpp \
  --extra go --extra php --extra perl --extra kotlin --extra clang)
```

The `rev-parse` result must equal the full SHA above. Prepare a Python interpreter with the target application's locked dependencies and test tools. The current native Spine adapters run Python application checks; a non-Python target requires an execution adapter before a four-arm correctness comparison.

## 2. Freeze one issue and its baseline

Copy `examples/framework-matrix.example.json` to `framework-matrix.json`. Set `source_repo` to an authorized **local** checkout, `baseline` to a committed pre-fix SHA, `task_file` to one saved issue JSON, `application_python` to the target's interpreter, and `checks` to real regression commands that pass on that baseline. Set `acceptance_checks` to independent commands that fail for the target behavior on the baseline and are kept outside the model worktree. Keep `frameworks` as the four built-ins and `passes` as `1`. Change `name` for every new attempt; work and result paths must be fresh and separate.

Use a read-only Jira or GitHub integration to save the issue once. Supported inputs include a Jira REST-shaped issue (see `examples/jira_issue.example.json`), an official SWE-bench row, or a local JSON object with `id`, `title`, and `description`. A repository URL in the config is for report identity; the runner does not push, open a PR, or edit Jira. Keep credentials outside the archive, configuration, and results.

Read the issue **before** measurement. Resolve missing prerequisites and consequential scope questions in a single written task/context that **all four arms receive**. For example, if an issue mentions an adjacent bug but does not say whether it belongs in the fix, record the owner's answer or choose a clearer issue. Do not invent the answer or give one arm extra information. Set `task_context` only to facts supported by the issue or a recorded owner decision; its supported fields are `problem`, `users`, `outcome`, `non_functional_requirements`, and `non_goals`.

For a non-interactive run, the example config uses `unresolved_question_policy: {"mode":"defer","owner":"benchmark-operator"}`. Replace that owner with the real person or team that will review the question. Every arm receives the same policy text; Spine writes any deferral into the generated proposal and reports it. A deferral **does not answer the question** and does not prove the resulting code correct. Use `question_answers` for exact, owner-approved answers known before the run; set `mode` to `stop` if unresolved scope must block implementation. The harness never invents an answer.

Name the owning public API and source file in the shared task, then set
`required_grounding` so `prepare` proves that pinned Spine's PKG context
contains them. Existing `test_*.py` files and configured check scripts are
frozen for every arm; the rule appears in each framework prompt. Preparation
also checks that independent acceptance fails for the target behavior on the
unfixed baseline. If a known fixed commit exists, set `known_fix_commit` to
its full SHA so independent acceptance must pass there. Inspect the
saved baseline failure output for unrelated setup errors.

## 3. Sign in, prepare, then run

Use a dedicated Codex login directory outside the source, work, and results directories. Sign in with your own account; the archive has no credentials.

```bash
mkdir -p "$HOME/.codex-spineharness"
CODEX_HOME="$HOME/.codex-spineharness" codex login
CODEX_HOME="$HOME/.codex-spineharness" codex login status
PYTHONPATH="$PWD/.local/spine-tools-v3.57.1/src" \
  .local/spine-tools-v3.57.1/.venv/bin/python -m unittest -q \
  test_framework_matrix test_matrix_study test_spine_feature test_scenarios
python3 framework_matrix.py doctor --config framework-matrix.json --smoke-model --approved
python3 framework_matrix.py prepare --config framework-matrix.json
```

The Codex **app** launches these local commands; the harness itself calls the Codex **CLI** using the dedicated ChatGPT sign-in above. The app's own login does not replace this CLI check. `doctor` checks local dependencies and makes one small model call **without repository or issue data** to verify model access; it consumes tokens outside the measured workflows. A green doctor is not a green application test. `prepare` then runs baseline regression checks without model calls. Inspect `results/<name>/PREPARED.json` and `TASK.json`. Confirm the exact baseline, issue text, CLI versions, checks, four arms, and source fingerprint. Then, after approving the selected repository/issue data transfer and expected model usage, run:

```bash
python3 framework_matrix.py run --config framework-matrix.json --approved
python3 framework_matrix.py package --config framework-matrix.json
```

The example sets `approve_checklist: true` so an authorized routine spec-kit checklist question does not pause the pilot. Change it to `false` if that continuation is not authorized. The runner will not overwrite an existing attempt. A run can take much longer than preparation; do not start a second issue while qualifying the first.

## 4. Read the result and handle failures

Open `results/<name>/COMPARISON_REPORT.html` or `.md`, then `RESULTS.md`, `EVIDENCE_VERIFICATION.json`, and each arm's `RESULT.json`, generated specification, and `implementation.patch`. `comparison-results.zip` is the shareable result archive; it excludes raw conversations and scans for credential-like text. It can still contain issue text and generated source, so treat enterprise results as confidential.

The report separates workflow completion, native Spine validation, independent acceptance, changed protected checks, recorded tokens, wall time, and **API list-price equivalent** cost (not a subscription charge). Passing selected checks does not prove complete correctness. Missing or interrupted response usage is unknown, never zero. One issue and one attempt per arm are diagnostic, not statistically significant. The runner prevents idle sleep on macOS and records both active and UTC elapsed time. A material gap stops later arms, preserves partial evidence, and writes `RUN_INVALID.json`; that attempt cannot be ranked or packaged. A fresh model-spending attempt needs authorization.

If an arm stops, inspect its log and failure marker. The Spine + OpenSpec adapter now applies frozen answers and named deferrals before the clarity gate; a remaining `questions_resolved` stop means the policy is `stop` or another question was not handled. Record an authorized scope answer and prepare a **new** matched experiment for all arms; do not edit the closed result or continue only one arm and call it equivalent. Interrupted runs have `INTERRUPTED.json` and cannot be packaged as completed comparisons. Preserve their partial evidence. For more tasks or the separate 33-scenario study, use [FRAMEWORK_MATRIX.md](FRAMEWORK_MATRIX.md) and [REFERENCE_MATRIX.md](REFERENCE_MATRIX.md) after this one-issue pilot is understood.
