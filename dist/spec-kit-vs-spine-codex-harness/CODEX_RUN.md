# Codex adapter and accounting

The external quickstart configures `CODEX_AUTH=app` and `SPINE_BACKEND=codex`.
Spec-kit uses a Codex agent session across specify, clarify, plan, checklist, tasks,
analyze, implement, and converge. Spine keeps its own orchestration and replaces its
LLM completion client with a harness-only Codex CLI adapter.

## Isolation and output

Each Spine completion uses a new empty directory and a fresh read-only Codex session.
The request contains the messages supplied by Spine. Shell, delegation, apps/plugins,
browsing, computer use, image generation, and memories are disabled. Observed tool
actions invalidate a completion. Spine applies returned file edits itself.

Forced-tool output uses a JSON `text` envelope, then validates the enclosed arguments
against Spine's original schema. Native `CODEX_OUTPUT_MODE=schema` is retained for
diagnostics but stalled during the pilot; use the default `envelope` setting.
The adapter supports one forced output tool, structured response schemas, and text/JSON.
It does not enforce Spine's requested temperature or maximum output-token limit.
Codex agent instructions add overhead, so this is a distinct experimental backend.

Spec-kit uses workspace-write confinement with network access; uv's cache is writable.
Children ignore personal user configuration and disable apps/plugins/delegation.
This is process/worktree isolation, not a separate OS account or a guarantee that model
context and generated code cannot contain sensitive data. Organizational policies remain
in effect. Do not put credentials into task text or benchmark fixtures.

## Authentication

Use a dedicated CODEX_LOGIN_HOME and sign in yourself, as described in QUICKSTART.md.
Subscription-mode Codex subprocesses remove API credential variables and force ChatGPT
authentication. The default package does not access the author's account or environment.
Keep credential storage outside results and never include it in a handback archive.

Official references checked for this handover:
- [Authentication](https://learn.chatgpt.com/docs/auth)
- [Non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode)
- [CLI installation](https://learn.chatgpt.com/docs/codex/cli)

## Accounting

Token counts use per-response `token_usage_record` entries deduplicated by response ID.
Inherited running totals are ignored. Input counts include cached reads; `uncached_input`
in report_usage.py subtracts cached reads and cache writes. Output includes reasoning;
do not add reasoning tokens a second time.

codex_usage.py contains an explicit standard short-context API rate snapshot checked
2026-09-29 at the [official pricing page](https://developers.openai.com/api/docs/pricing).
It covers GPT-5.6 Sol, GPT-6 Sol, and GPT-6 Astra. Availability is account-dependent.
To add another model, verify its published input, cached-input, cache-write (if applicable),
and output rates; add its exact model ID and source/date. Unknown models fail rather than
silently being priced at zero. Longer-context and other pricing regimes require separate
repricing; reported cost is not an actual ChatGPT subscription invoice.

Run report_usage.py only after all children have stopped. It reads exported sessions
under the named results directory and excludes diagnostic folders. It has no dependency
on a personal home-directory script. Missing/unexported interrupted responses cannot be
reconstructed; inspect usage.json, summary.json, and failure logs before calling usage
complete. Intake summaries count successful completion returns, so failed/retried calls
may make the exported ledger total larger than the summary total. Preserve and report
that distinction rather than dropping failed-attempt cost.

## Reproducibility and limitations

The built-in tickets, codegen implementation, and graders are imported from the pinned
Spine trees. JSON catalogs extend those tickets in memory without patching the repository;
all three runners receive identical selected specifications and held-out test contents. Their Python dependencies come from those trees' uv.lock files; no separate
pip requirements file is required. setup.sh installs dev/MCP extras needed by the harness.
Spec-kit is downloaded at the pinned tag for each initialized run; Codex is an external CLI.

The historical API and Claude runners remain included, but the quickstart only validates
the OpenAI subscription route. Switching backends changes the experiment and should use
new result directories. The original measured results and private pilot logs are excluded.

summarize.py retains the historical exploratory run-level tests for compatibility.
Those p-values and bootstrap intervals do not correct for repeated tickets or repository
clustering. Use raw summaries and the protocol in METHODOLOGY.md for a defensible broader study.

Use `report_results.py` for the supported scenario-level analysis in this release. It matches intake by ticket/pass and does not report independent-run p-values. See SCENARIOS.md for task authoring and the inherited fit rules.
