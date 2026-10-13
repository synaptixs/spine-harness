# Run both benchmark arms with a Codex subscription

This copy adds `SPINE_BACKEND=codex`. Spec-kit uses its existing Codex CLI workflow;
Spine's intake and codegen use a harness-only completion adapter. No API key is used.
The original ZIP on the Desktop is unchanged. This is a new experimental configuration,
not a reproduction of the published direct-API cost ratios.

The local `.env` points at a separate clone of the existing Spine repository in
`/private/tmp/spineharness-20260929`. The source checkout is unchanged. The target
is `bd16dbb7`; Spine is `v3.52.0`; spec-kit is `v1.0.11`; corrected grading is `a6ac7c34`.

## Authentication and execution

The initial run reused the existing ChatGPT login by copying its authentication cache
into the isolated `CODEX_LOGIN_HOME` (directory mode 700, file mode 600). The original
login/configuration was not edited. Credentials are outside the project and results.
If the copied login expires, sign in independently:

```sh
source .env
CODEX_HOME="$CODEX_LOGIN_HOME" codex login
```

The app's command sandbox restricts network access by default. Model runs and dependency
installation need the app's normal permission approval for network access. The Codex
children retain their own read-only (Spine) or workspace-write (spec-kit) sandbox.

```sh
source .env
bash setup.sh
uv run --frozen --project "$WORK_DIR/spine-code" python -m unittest -v test_codex_backend
python3 run_comparison.py --dry-run --models gpt-6-sol --passes 1 --parallel 1
python3 run_comparison.py --models gpt-6-sol --passes 1 --parallel 1 --cap 25 --job-cap 20
python3 summarize.py
```

The pilot uses only `NEW-SEVSUMMARY-1`. For a new run, choose fresh WORK_DIR and RESULTS_DIR,
keep SPINE_REPO and CODEX_LOGIN_HOME, and rerun setup. Do not delete old trees to retry.
The runner propagates subprocess failures and creates JOB_FAILED rather than claiming success.
QUOTA_STOP means the subscription limit or a provider quota was reached.

## What the adapter preserves and changes

Spine still supplies context, builds its graph, designs, applies generated changes, runs
tests, refines, and grades. Each completion starts a fresh Codex session in an empty
directory. Shell, delegation, apps/plugins, browsing, and computer use are disabled;
any observed tool action invalidates the completion. No benchmark checkout is supplied
as Codex's working directory. This is experimental context isolation, not a separate OS user.

Spine's forced output tool is returned as serialized JSON inside a strict `text` envelope,
then parsed and validated against Spine's original argument schema before use. Native
`CODEX_OUTPUT_MODE=schema` is retained for diagnostics, but repeated implementation calls
stalled in that mode; the equivalent envelope diagnostic returned in about 26 seconds.
The adapter supports one forced tool, Pydantic response schemas, and text/JSON completions.
Unsupported multi-tool contracts fail explicitly.

Codex still adds agent instructions and token overhead. Spine's requested temperature
and output-token limit are recorded but not enforced by this adapter. Both arms use
explicit `high` reasoning. These differences prevent treating this as the original API experiment.

Tokens come from `token_usage_record`, deduplicated by response ID, with cache reads/writes
kept separate. `codex_usage.py` records the price basis. USD is a **standard short-context
API list-price equivalent**, not an invoice or an estimate of subscription charges. Rates
were checked at https://developers.openai.com/api/docs/pricing on 2026-09-29. The current
listed GPT-5.6 Sol rate differs from the original harness's catalog rate; historical
dollar figures should not be directly compared without repricing both datasets.

`--cap` is a pass admission budget, and `--job-cap` checks between spec-kit steps.
Neither is a hard ceiling: a running step can overshoot. Plan usage limits also apply.

One ticket tests functionality only. Report raw outcomes and usage before drawing any
performance conclusion. Authentication probes and adapter development are separate from
measured benchmark work.

After the benchmark children have exited, use the same personal session calculator
against the isolated log root:

```sh
python3 measure_closed_run.py --model gpt-6-sol --since <UTC-start> --until <UTC-end>
```

The wrapper changes the log root and applies the verified price snapshot in memory;
it does not edit the shared calculator. This counts completed benchmark sessions,
not the still-open Codex chat used to develop the adapter.

Official documentation:
- https://learn.chatgpt.com/docs/non-interactive-mode
- https://learn.chatgpt.com/docs/auth

The pilot overlapped spec-kit with the corrected Spine run while diagnosing timeouts.
Wall times are descriptive, not a controlled sequential comparison. Abandoned attempts
and the response-format probe are retained under results diagnostics and excluded from
measured arm summaries; interrupted responses have unknown total usage.

## Checklist pauses and the pilot result

The pilot proves that both workflows can call GPT-6 Sol through ChatGPT authentication.
Spine completed NEW-SEVSUMMARY-1 and passed the functional and held-out tests, but its
new files made three documented repository counts stale, failing the repository gate.
Spec-kit completed planning and paused before implementation at 20 unchecked reviewer
checklist items. This is not a completed head-to-head comparison. See
[the pilot report](results/pilot-20260929/PILOT_REPORT.md).

The runner now recognizes the actual checklist wording and pauses by default.
`--approve-checklist` must only be supplied after explicit user approval of proceeding
with unchecked items. Automatic approval review rejected the initial recovery attempt;
no recovery model call ran. After obtaining that approval, resume the saved session with:

```sh
source .env
uv run --frozen --project "$WORK_DIR/spine-code" python speckit_codex.py \
  gpt-6-sol NEW-SEVSUMMARY-1 1 --cap 20 --resume-checklist --approve-checklist
```

Recovery preserves the original summary and includes all previous planning usage.
It does not check off reviewer items. The final grades and cost report must be regenerated
after recovery closes. To account only for exported pilot sessions, excluding diagnostics:

```sh
python3 measure_closed_run.py --model gpt-6-sol --measured-only \
  --since 2026-09-29T12:00:00Z --until <UTC-end-after-model-processes-exit>
```
