# Default 33-scenario reference matrix

`reference_matrix.py` runs the 3 original reference tasks and the 30 tasks in
[`catalog/expanded.json`](catalog/expanded.json) through four workflows:

| Arm | Workflow |
|---|---|
| `speckit` | spec-kit plan and implementation through Codex |
| `openspec` | OpenSpec proposal/spec and implementation through Codex |
| `spine-openspec` | Spine + PKG drafts OpenSpec, then consumes that change through native `run_feature` |
| `spine-pkg` | Native Spine + PKG `run_feature` from the same task, without OpenSpec |

One pass is **33 × 4 = 132 ticket-arm measurements**. Each arm gets a disposable
copy of the same committed reference baseline, the same model/reasoning setting,
and the same benchmark-author task text. The original application checkout is
unchanged. The catalog's held-out Python tests are frozen outside model worktrees
and run only after each arm finishes. `scripts/state-numbers.py --check` is the
shared baseline regression gate. Native Spine's own generated tests and bounded
refinement are measured within its workflow; they are distinct from held-out
acceptance. The 33 tasks share one repository and are not 33 independent projects.

## Run

Follow [`QUICKSTART.md`](QUICKSTART.md) in the source checkout (or
`REFERENCE_QUICKSTART.md` in the external archive) to install Git, Python/uv, Codex,
Node/npm and OpenSpec, clone Spine, sign in with a dedicated Codex login home,
and run `setup.sh`. Use a Spine revision with the OpenSpec intent-extraction fix
for `spine-openspec`; the historical v3.56.0 tag can fail its clarity gate even
when the task states problem, users, and outcome. Freeze the exact `SPINE_REF`
and checkout before preparing. `setup.sh` checks out that ref for both native
Spine arms; the runner records its full SHA.

```bash
source .env
python3 reference_matrix.py dry-run --model "$MODEL" --passes 1
python3 reference_matrix.py prepare --model "$MODEL" --passes 1
# Inspect $RESULTS_DIR/reference-matrix/MATRIX_PLAN.json and prepared checks.
python3 reference_matrix.py run --approved
```

`dry-run` lists the task/arm schedule without writing or calling a model.
`prepare` freezes the selected task bodies, held-out tests, source fingerprint,
CLI versions and per-task configs; it performs offline baseline checks only.
`run` is sequential, refuses an active duplicate, and skips already closed task
results if interrupted between scenarios. It does **not** restart an interrupted
task attempt or overwrite measured output. Choose fresh `WORK_DIR` and
`RESULTS_DIR` for a new study. The runner has no hard model-spend cap; begin
with `TICKETS=NEW-SEVSUMMARY-1` and one pass to verify your environment before
the full 132-measurement workload.

Closed per-task results appear at
`$RESULTS_DIR/reference-matrix/runs/<scenario>/COMPARISON_REPORT.md`, alongside
`RESULTS.json`, patches, stage ledgers, frozen check copies and validation
evidence. The batch-level `study/MATRIX_STUDY_REPORT.md` and
`MATRIX_STUDY_RESULTS.json` compare all four arms across tasks. A passed command
is a selected functional check, not proof of complete correctness. Missing
response usage stays unknown; dollar figures are **API list-price equivalents,
not subscription charges**. One attempt per task does not estimate run-to-run
variance or prove that PKG caused a difference.

`run_comparison.py` and `report_results.py` remain for reproducing the prior
two-arm 33-scenario protocol. Their separate intake measurements and legacy
grader are not pooled with this four-arm native-Spine matrix.

For a study across **different public projects**, use `framework_matrix.py`
once per task/repository and combine the closed result directories with
`matrix_study.py`. The final report separates repositories and shows selected
correctness, recorded tokens, workflow and total wall-clock time, and API
list-price equivalent cost for each arm. See
[`FRAMEWORK_MATRIX.md`](FRAMEWORK_MATRIX.md#multiple-application-repositories).
