# Framework matrix: Jira and SWE-bench tasks

`framework_matrix.py` is the multi-framework path. The historical `benchmark.py`
and its saved results remain unchanged. This path compares **spec-kit**,
**OpenSpec standalone**, **Spine + PKG + OpenSpec**, **Spine + PKG without OpenSpec**, and external frameworks under one task,
baseline, model, and set of checks. Each framework gets a separate disposable
clone. The original repository and Jira are read-only.

For an external machine, begin with [MATRIX_QUICKSTART.md](MATRIX_QUICKSTART.md):
one repository, one issue, and four built-in workflows. The handover includes a
self-contained Git bundle for published Spine 3.57.1. The public pilot used an
earlier pre-release commit; its results are historical and retain that pin.
The application checkout is separate. A successful setup does not guarantee
every issue will clear native workflow gates.

The default **33 reference scenarios × four built-in workflows** are orchestrated
by `reference_matrix.py`; see [REFERENCE_MATRIX.md](REFERENCE_MATRIX.md). This
single-task interface remains the route for Jira, SWE-bench, and user-provided frameworks.

## Multiple application repositories

The application under test is `source_repo`, not the Spine tools checkout.
Use one frozen task, baseline commit and configuration per repository/issue;
prepare dependencies and selected checks for that application's disposable clone.
Closed task directories can be combined across repositories:

```bash
python3 matrix_study.py --results results/ontomesh-issue results/spine-pkg-issue \
  --output results/cross-repository-study
```

Give each config a `repository_url` or stable internal repository identifier. The aggregate groups outcomes by
repository and identifies tasks with a repository/task pair, so equal issue IDs
in different projects remain distinct. Original GitHub repositories are never
pushed to and no pull requests are opened by measurement. Proposed changes are
saved as patches; optional review PRs should use dedicated test forks and be
kept outside the measured workflow. The current native feature adapter runs
Python application checks; C, Java, PHP and other repositories need a reviewed
language-specific execution adapter and acceptance suite before they can enter
the four-arm correctness comparison. PKG extraction may support more languages,
but extraction support alone does not make their code-generation checks runnable.

## Public pilot, then private enterprise repositories

Use public repositories to exercise setup, isolation, artifact capture, and the
four-arm report. Treat those runs as harness qualification, not as a proxy for
enterprise performance. The later enterprise study should run on an authorized
machine with a local clone of each private application repository, a frozen
pre-fix commit, a saved issue snapshot, and independently authored checks. The
runner reads `source_repo` locally and makes disposable clones; it does not
require a public GitHub URL or open a pull request. Use the same task text,
baseline, model/settings, dependency image, and checks for all four arms.

Results are **confidential** for private tasks. `TASK.json`, generated specs,
patches, check logs, and the results ZIP can contain proprietary code and issue
text. The credential scanner only checks for credential-like patterns; it is
not a data-loss-prevention or source-code redaction system. Keep work/results,
Docker images, and archives on approved storage, and review any export before
sharing. The Codex model call receives task text and relevant source; verify
the organization's model/data-use authorization before a private run.

Separate public and private populations in the report. Record repository,
baseline commit, task origin, task sampling rule, framework/tool versions,
model/settings, test provenance, run count, and any shared prerequisites. For
larger studies, report paired per-task differences, repository-level summaries,
and uncertainty; do not treat many related issues from one repository as
independent projects.

## What the results measure

| Measure | Recorded definition | Limit |
|---|---|---|
| Token usage | Sum of closed per-response input and output tokens, including cached input once; stages reconcile to the response ledger. | Missing/interrupted response usage makes the full total unknown. |
| Workflow wall time | Monotonic elapsed seconds from starting an arm's implementation worker to its return/failure. | Excludes disposable clone creation and post-run checks; total wall time records those too. Neither is model-only latency. |
| Selected correctness | Configured baseline regression and frozen post-run acceptance commands pass, with protected check inputs unchanged. Native Spine status is shown separately. | Covers selected behavior, not complete issue correctness; official SWE-bench resolution requires its evaluator. |
| Cost | Sum of recorded responses at published model API list prices, with long-context pricing checked per response. | **API list-price equivalent, not a ChatGPT subscription charge or invoice**; unknown usage/pricing stays unknown. |

Each task writes `COMPARISON_REPORT.md`/`.html`, `RESULTS.json`, response-use
evidence, stages, generated specifications, implementation patch and integrity
verification. `matrix_study.py` writes a four-workflow overview, per-repository
breakdown, per-task rows and paired token ratios. Its sign test collapses tasks
within each repository; one repository cannot support a cross-project
significance claim. No model call is needed to regenerate a closed report.

## Inputs and preparation

Copy `examples/framework-matrix.example.json` to `framework-matrix.json`, then
fill in the local source checkout, committed baseline, task snapshot, dedicated
Codex login home, application Python, and relevant commands. The task file is
one of:

- A saved Jira REST issue `{ "key": "TEAM-123", "fields": { "summary": ..., "description": ... } }`.
  A saved MCP envelope is also accepted. Set `acceptance_field` in the config
  if criteria live in a Jira custom field.
- One official SWE-bench dataset instance JSON, including `instance_id`,
  `repo`, `base_commit`, and `problem_statement`. The runner passes only the
  problem statement to frameworks; `test_patch` and test result fields are
  omitted from the public `TASK.json`.
- A local `{ "id", "title", "description" }` task.

For an official instance, install the optional `datasets` package and set
`task_file` to a fresh path outside the application checkout, then fetch one
row before preparation:

```bash
python3 framework_matrix.py fetch-swebench --config framework-matrix.json \
  --dataset-name SWE-bench/SWE-bench_Verified --instance-id owner__repo-12345
```

The raw local snapshot retains the official row for provenance, including its
gold and test patches. The public `TASK.json` and every framework prompt omit
those fields. Replace the example instance ID with an actual ID in that dataset.

Do not combine unrelated issue baselines in one matrix. For a SWE-bench instance,
checkout the instance's `base_commit` locally and set `baseline` to that exact
commit. The official dataset's test patch must remain outside the framework's
working tree. Dependencies and regression commands must be prepared before
measurement; this harness currently assumes a Python application for native
Spine checks. `acceptance_checks` are post-run diagnostics, never model feedback.
Absolute local acceptance scripts named in those commands are hashed and copied
to `frozen-acceptance/` during preparation. A changed script blocks the model
run; the report checks it again after closure.
Use `{config_dir}` in a check argument for a script saved beside the config;
the loader resolves it to the config directory before freezing the input.

`prepare` runs independent acceptance on the unfixed baseline. At least one
command must fail with exit 1 while no command may fail to start or report a
setup error. If a known fixed revision is available, set `known_fix_commit` to
its full SHA; preparation checks that independent acceptance passes on an
isolated clone of it. Review the saved diagnostics to confirm the
baseline failure is the target behavior, not an unrelated assertion. Existing
`test_*.py` files and configured check scripts are frozen in all four arms;
new tests belong in new files. This boundary is supplied to every framework.

For native Spine arms, set `required_grounding` to the issue's exact owning
symbols and repository-relative source files, for example
`{"symbols":["RepoCodeExtractor.extract"],"files":["src/spine/extractor.py"]}`.
Preparation checks that the symbols occur in the shared task, the files exist,
and the pinned Spine version's deterministic PKG context contains both before
any model call. A failed gate is saved in `PREPARATION_FAILED.json`; correct
the task or Spine retrieval and prepare a fresh experiment.

For tickets with terse descriptions, set the optional `task_context` object in
the config with `problem`, `users`, `outcome`, `non_functional_requirements`,
and `non_goals` as plain text. It is frozen into `TASK.json` and supplied to
**every** arm, including Spine's draft input. Do not infer missing business
facts to force a pass. The earlier unpatched Spine 3.56.0 could omit the named why fields
from its OpenSpec proposal and fail its own clarity gate. Spine 3.57.1 includes the
intent-extractor fix that preserves explicitly stated problem, users, outcome,
and non-goals. A fresh Spine + PKG + OpenSpec PILOT-1 run on that source fix
passed the clarity gate, generated code, and passed the selected regression and
feature-acceptance commands. This is one synthetic task, not a guarantee for
other tasks. See `results/pilot-ranked-search-spine-fixed-20261008/`.
If the issue mentions an adjacent defect but leaves its inclusion unclear,
record an owner-approved scope answer in the shared task before preparing any
arm, or choose a clearer issue. In the public #456 pilot, Spine + OpenSpec
stopped before implementation because its generated proposal raised such an
unresolved question. That is a native clarity outcome, not an OpenSpec CLI
installation error. The updated adapter accepts `question_answers` (exact
recorded answers) and `unresolved_question_policy` (`stop` or a named `defer`
owner). Both are frozen into the shared task and seen by all arms; the
Spine + OpenSpec arm records them using Spine's native answer API before the
gate. A deferral clears the question gate but supplies no answer. The report
lists every recorded answer or deferral. Do not auto-answer the question for
one arm or resume only that arm and present it as a matched first attempt.

Install the official OpenSpec CLI with Node/npm (pin a chosen release with
`npm install -g @fission-ai/openspec@<version>`), the Codex CLI, `uv`/`uvx`,
and a Python application environment before `prepare`. The matrix records the
actual CLI versions. For either native Spine arm, `tools_dir` must be a separate Spine
checkout with its frozen `uv` environment. Set `spine_commit` to its full commit
SHA and `spine_ref` to a human-readable version or branch; `prepare` verifies
the checkout against that pin. The current two-arm and four-arm examples pin
published Spine 3.57.1, including the OpenSpec intake, coverage, and judge
evidence fixes. Keep the bundled commit and `spine_ref` together when moving
to an external machine. Use the package's
established `benchmark.py bootstrap` flow if you already have its Jira config,
or prepare that pinned checkout directly. External adapters can declare a
`version_argv` command so their version appears in the report.

```bash
python3 framework_matrix.py prepare --config framework-matrix.json
# inspect PREPARED.json, TASK.json and the common baseline
python3 framework_matrix.py run --config framework-matrix.json --approved
python3 framework_matrix.py package --config framework-matrix.json
```

`fetch-swebench` and `prepare` make no model calls. `prepare` refuses an
existing work or results directory.
If a baseline check fails, its command and diagnostic are saved as
`PREPARATION_FAILED.json` in the work directory; use a fresh experiment name
after fixing the environment.
On macOS, `run` holds an idle-sleep assertion during measurement and records
both monotonic active time and UTC elapsed time for each arm. A material gap
stops later arms and writes `RUN_INVALID.json`; the partial report preserves
evidence but cannot be packaged or used for a ranking. A genuine workflow or
framework failure under a complete protocol remains a valid recorded outcome.
`run` also refuses a duplicate attempt. The `--approved` flag records that the
operator reviewed the task/baseline and authorized sending the selected text and
disposable source to the model. The four built-in arms use the same configured
Codex model, reasoning effort, and isolated ChatGPT login. Both native Spine arms
require `tools_dir` at the configured Spine commit and `application_python` with the
project dependencies. Their workers run under the pinned Spine checkout's
`.venv/bin/python`, so Spine's own dependencies are available even when the
harness entry point uses system Python. `openspec` requires the OpenSpec CLI and initializes its
Codex skills inside only its disposable clone. `speckit` uses the pinned spec-kit
CLI. External adapters receive placeholders `{repo}`, `{task}`, `{output}`,
`{model}`, and `{login_home}` in an **argv array**, never a shell string.
Set `approve_checklist: true` only when the operator explicitly authorizes
continuing through routine spec-kit checklist questions; otherwise that arm
stops and preserves its evidence if such a question occurs.
After `$speckit-analyze`, the harness reads the full analysis report. HIGH or
CRITICAL findings trigger up to two spec/plan/task remediation passes and a
fresh analysis before implementation. `ANALYSIS_GATE.json` records each review.
An absent report, an unresolved operator choice, or findings remaining after
those passes stop the Spec Kit workflow before implementation. Remediation
must preserve the frozen task and its recorded answers.
Spec Kit copies recorded clarification questions and answers verbatim. If its
spec records a different question, the matrix stops all later arms and marks
the partial comparison invalid. Record an owner-approved answer for that exact
question in a fresh shared config before another model-spending attempt.

An external adapter writes its patch into `{repo}` and may write `{output}/USAGE.json`:

```json
{
  "model": "gpt-6-sol",
  "reasoning_effort": "high",
  "stages": [
    {"name": "plan", "complete": true,
     "responses": [
       {"response_id": "provider-response-1",
        "usage": {"input_tokens": 1000, "cached_input_tokens": 200,
                  "output_tokens": 100}}
     ]}
  ]
}
```

Response IDs must be unique across stages. The harness computes totals and
API list-price equivalents from those records. If a stage has no verified
responses, usage is **unknown**, never zero. External adapters should retain
their raw response ledger locally for independent reconciliation and should
not put credentials in the result directory. A successful command exit means
the workflow ran; patch correctness is measured separately.

The output has `COMPARISON_REPORT.md` and a self-contained
`COMPARISON_REPORT.html`, `RESULTS.md`, `RESULTS.json`,
`EVIDENCE_VERIFICATION.json`, a conversation-free `USAGE_EVIDENCE.json`, each arm's full
`changes.patch`, code-focused `implementation.patch` and specifications, stage usage, baseline and post-run checks,
and a credential-scanned `comparison-results.zip`. The report lists generated
production and test files as the observed edit surface. For Spine, this is not
a complete Product Knowledge Graph blast-radius count. Model use and check
outcomes are separate. One pass per task is descriptive; add independent tasks
and repeats before claiming a stable population effect.

## Official SWE-bench evaluation

There are two distinct uses of SWE-bench here. For an **official public
SWE-bench instance**, `fetch-swebench` saves the selected dataset row,
`prepare` verifies its `base_commit`, the four arms generate patches, and
`export-swebench` writes one prediction JSONL per arm/pass. The official Docker
evaluator determines `resolved`; the framework's exit code and local checks
do not. The gold patch and `test_patch` stay out of model-visible task input.
The official evaluator is an optional post-run step and has not yet been
validated end-to-end on this harness's four-arm path.

For **private enterprise issues**, use a SWE-bench-style protocol: one
pre-fix commit plus issue text, identical isolated attempts, a patch from each
arm, and frozen independent tests in a reproducible environment. These are
private benchmark results, not official SWE-bench Verified scores. Current
`evaluate-swebench` is wired to an official dataset instance and cannot grade
an arbitrary private Jira task. SWE-bench's current CLI supports local task
repositories with a task manifest, Dockerfile, evaluation script and tests;
connecting that route to this harness needs a private task-repo adapter and
end-to-end validation before using its verdict in an enterprise report.
Keep private task repos and images local; publishing a dataset or submitting
to a leaderboard is a separate action.

For an official instance, export each arm's prediction after the model run:

```bash
python3 framework_matrix.py export-swebench --config framework-matrix.json
python3 framework_matrix.py evaluate-swebench --config framework-matrix.json \
  --prediction results/<name>/swebench-predictions/openspec-pass1.jsonl \
  --dataset-name SWE-bench/SWE-bench_Verified
```

Install `swebench` and Docker separately. Select the dataset that actually
contains the frozen instance. The runner passes a distinct patch-derived
`run_id` and `--instance_ids` to the [official evaluator](https://github.com/SWE-bench/SWE-bench/blob/main/docs/guides/evaluation.md).
The official evaluator determines whether the patch resolves the instance;
its process exit alone does not. Inspect its instance report before writing a
resolved score. The exported JSONL follows the official `instance_id`,
`model_name_or_path`, `model_patch` prediction contract. Jira tasks can use the
same isolated-patch and frozen-check method, but they are **not** official
SWE-bench results. Framework metadata under `.agents/`, `.codex/`,
`.specify/`, `openspec/` and `specs/` remains in the full evidence patch but
is omitted from the official prediction patch. Generated `tests/`, `test/`,
`test_*.py`, and `conftest.py` changes are likewise retained as evidence but
excluded from that prediction, so a framework cannot submit its own tests as
part of a SWE-bench fix.

OpenSpec's Codex commands and CLI validation are described in its
[official command reference](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md)
and [CLI reference](https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md).
The first real paid run on a new external environment should start with one
small issue and inspect each arm's setup, session ledger, specs, patch and
post-run checks before scaling to a larger matrix.

## Compare multiple tasks

Use a fresh matrix config/result directory per independent Jira issue or
SWE-bench instance. After at least two tasks close, combine their evidence:

```bash
python3 matrix_study.py --results results/task-a results/task-b \
  --output results/my-multi-task-study
```

`MATRIX_STUDY_REPORT.md`, its self-contained HTML companion, and
`MATRIX_STUDY_RESULTS.json` show per-framework
completed measurements, token and cost totals with explicit complete-usage
denominators, workflow wall time, selected-check outcomes, official SWE-bench
resolved counts when available, and paired token ratios. The two-sided exact
sign test collapses repeated passes and tasks within each repository. The
rollup rejects duplicate repository/task pairs or mixed task types, models,
framework versions, or pass counts. It deliberately
does not use a token p-value as evidence of functional equivalence, population
generalization or PKG causality.
