# Spine development roadmap for completion without human repair

Prepared October 5, 2026. Status: proposed implementation plan, grounded in the ONTM-4 evidence and inspected source. Intended owners: Spine development and harness validation teams; role assignments below are proposed, not assigned people.

Deliver a first release that detects missing default behavior and performs bounded automatic refinement before returning a completed result. **Planning commitment: seven to ten working days for a single engineer** (confirmed in grilling round 1, 2026-10-05). The "two engineering days to a working milestone / five working days to a release candidate" figures from the original draft hold only as a best case with two engineers and no surprises — they are not the headline number and should not be quoted as the delivery target. Broader benchmark evidence follows the release candidate and depends on runtime capacity.

The target is **no human diagnostic intervention after a run starts**. Automatic repair within the normal workflow is allowed and its full consumption is counted. This does not promise that the first model response will be correct.

## Evidence and existing implementation

ONTM-4 exposed two related integration omissions: default rule loading did not invoke the supplied compiler, and physical column facts needed logical property aliases for compiled rules to match. Six generated tests passed with explicit rule sources and substituted parser/inference implementations. They did not establish that the default path produced derived results. One additional native Spine refinement corrected the demonstrated gap. Both saved outputs then passed the seven selected checks. See the [validated changes](results/ontm4-benchmark-20260930/CONTINUATION_VALIDATION.md) and [comparison report](results/ontm4-benchmark-20260930/COMPARISON_REPORT.md).

The repair already exists as an Ontomesh patch. The development task here is to improve Spine and the harness so this class of failure is detected automatically on other repositories. Do not hard-code Ontomesh symbols or copy its application repair into Spine.

The inspected Spine checkout at commit `5de62735339437f6c9d1bc7dc698391f9db52063` already has `implement`, `author_tests`, and `refine`, with a benchmark refinement cap defaulting to three. This differs from the frozen benchmark version; pin the intended development baseline before coding. The temporary historical checkout no longer contains its benchmark script, so reproduce historical behavior from pinned source and saved evidence rather than assuming that checkout is intact.

| Existing component | Development implication |
|---|---|
| Spine `scripts/codegen_benchmark.py`, `run_ticket` | Extend its existing generated-test and preflight loop; keep independent evaluation outside feedback. |
| Spine `src/orchestrator/sdlc/codegen.py`, `LLMCodegenAdapter` | Add required behavior context to implementation, test generation, and refinement; avoid a second code-generation pipeline. |
| Spine `src/orchestrator/sdlc/grounding.py`, `PKGCodegenGrounder` | Add a bounded integration-path view using available repository evidence. |
| [project_adapter.py](project_adapter.py), `ProjectAdapter.install` | Today `all(...)` over no configured checks passes internal preflight. Project mode still reports correctness unverified. Introduce explicit validation status rather than interpreting an empty list as functional evidence. |
| [spine_pkg.py](spine_pkg.py) | Preserve execution locks, native stage accounting and disposable changes; distinguish execution completion from verified behavior. |
| [report_project.py](report_project.py) and [report_results.py](report_results.py) | Present gate outcomes, automatic repairs, human interventions and all attempt consumption explicitly. |

## Delivery sequence

| Milestone | Target from start | Proposed owner | Deliverable and release gate |
|---|---|---|---|
| G0 `spineharness` repo + CI prerequisite | Days 1 (before WP1 starts) | Harness/test engineer | `spineharness` becomes its own git repository (it is currently an untracked-for-this-purpose subdirectory of an unrelated monorepo) with a minimal lint+test CI gate mirroring `ai/spine`'s pattern. Blocks M1 and M3, whose acceptance criteria assume adapter tests and CI evidence exist. |
| M1 Required behavior gates | Days 1–3 | Harness/test engineer, with Spine engineer integration | Versioned public behavior manifest, deterministic fixture and native repair integration. Known broken default loading fails; corrected implementation passes. No empty or skipped mandatory suite can count as passed. |
| M2 Reliable automatic completion | Days 3–5 | Spine engineer | Required gates control native refinement, budgets and terminal status. A scripted failing implementation is repaired without human feedback; exhausted or blocked runs return incomplete evidence. Must include the measured `blast_radius` of `LLMCodegenAdapter` (115 callers / 180 touches, including the three production callers `feature_runner.run_feature`, `worker._build_codegen`, `live_sdlc_worker.main`) as an acceptance artifact, plus a regression test per production caller, and a stated rollback: an unverified/legacy project must take the same `refine()` code path as today — the gate is additive, not a branch. |
| M3 Better grounded implementation and tests | Days 5–7 | Spine engineer; test engineer reviews | Compact evidence of entry points, existing components and expected outputs; real default-path tests and controlled negative cases. |
| M4 Reproducible release candidate | Days 7–10 | Both roles | Closed-session accounting, reports, compatibility checks, updated quickstart and portable packages. All offline release tests pass. |
| M5 Independent validation | Following week, capacity dependent | Benchmark owner and an independent reviewer outside the M1–M4 builder roles | Frozen paired evaluation on unseen issues; publish observed success, intervention and cost results with uncertainty. Go/no-go threshold is pre-registered before this milestone starts, not chosen after seeing results. This is a separate evidence milestone and a separate SSPN epic from M1–M4. |

Critical path: G0 → define public gates → execute them → route failures into native refinement → freeze the final candidate → run hidden evaluation. Grounding improvements can follow the first working gate; do not delay delivery for a comprehensive graph redesign.

## Work packages and acceptance criteria

### Work package 1 Define required behavior evidence

Add a versioned behavior manifest to the project profile, with stable requirement IDs, source acceptance text, public entry point, default configuration, fixture, expected observable result, command as an argv array, timeout and whether the check is required. Map every in-scope acceptance criterion to a check or an explicit unresolved limitation. Initial scope is Python external projects; other languages require their own runner adapters.

Separate three sets: public development checks whose failures can drive repair, immutable regression checks, and hidden evaluation checks revealed only after the final candidate is frozen. Required checks and their expected assertions must be controlled outside the model's editable tree, with hashes verified before and after execution. Model-generated tests supplement this contract; they cannot redefine it.

Proposed implementation: extend `ProjectAdapter.read`, add a reusable `behavior_validation.py` runner and new adapter tests. Preserve existing token-only profiles as an explicit legacy mode whose functionality status remains unverified. A profile opting into verified completion must have nonempty required checks. Report missing, skipped, zero-collected, errored and timed-out checks separately; none satisfy a required pass.

Acceptance: a small fixture returns the expected derived output through its default entry point. Disconnecting its compiler or removing required property mapping causes a behavioral assertion failure even when the command exits successfully. Use ONTM-4 as a development regression only; its seven revealed checks are no longer unseen evaluation evidence.

### Work package 2 Put required gates inside native refinement

Extend the native loop so successful completion requires generated tests, mandatory public behavior checks and required regression checks to pass. Run checks after the initial implementation and each refinement. Feed concise structured failures into `LLMCodegenAdapter.refine`: requirement ID, command, expected result, actual result and relevant trace. Keep full logs as artifacts. Revalidate required behavior after every change; do not rely on a pass from an earlier revision.

Use proposed terminal statuses `verified_selected_behaviors`, `validation_failed`, `blocked_environment` and `budget_exhausted`, separate from process status. “Verified” means the declared checks passed, not full production certification. Missing fixtures or unavailable dependencies are environment blockers; an empty result violating a behavior assertion is a feature failure. Determine this from execution evidence, not the model's description.

Proposed initial policy: at most three refinement iterations, configurable per-call timeout, and a run-wide token/time budget declared before launch. Count transport retries and child model calls separately from refinement iterations. Refuse another call when the budget is exhausted; record any in-flight overshoot and unknown interrupted usage. Persist checkpoints and reuse the existing exclusive execution lock so resumption cannot duplicate a completed call or overwrite a result.

Acceptance: offline scripted model responses demonstrate fail → native refine → pass; persistent failure reaches the cap; environment failure is classified correctly; cancellation/resumption preserves accounting; tampering with checks fails validation; no hidden evaluator text appears in any model request. Expose the same validation policy through the relevant production orchestration path before advertising this as a general Spine capability, rather than only a benchmark feature.

### Work package 3 Supply integration evidence and realistic tests

Extend PKG context to describe the requested public entry point, existing loader/compiler/service symbols, relevant data mappings, configuration defaults and observable output. Include file/symbol references and the indexed commit. Use actual graph relationships where supported; verify gaps through bounded source inspection. Mark unresolved or dynamic edges explicitly. PKG supplies repository evidence; static extraction alone does not prove runtime behavior.

Pass a compact requirement-to-path mapping to `implement`, `author_tests` and `refine`. Refresh affected grounding after edits. Keep the context bounded and record its size so the new safeguards do not silently erase the efficiency benefit.

For required integration tests, use real internal components and deterministic fixtures. Substitute external LLM/network boundaries when necessary. Each required default-path check must assert a meaningful output and test the relevant disable/override behavior. Unit tests may still use stubs; they must not be the only evidence for integration completion.

Acceptance: the fixture covers both a missing default dependency and mismatched physical/logical property names. Controlled defects make the required check fail, while the intended implementation passes. Record this evidence in CI. A general scanner banning all mocks is out of scope; it would reject legitimate unit tests without proving integration coverage.

### Work package 4 Ship accounting and reports with the gate

Add per-stage usage and outcomes for grounding/design, implementation, test generation and every automatic refinement. Deterministic work may have zero model tokens while still having runtime; label it accordingly. Record requested and observed model, reasoning setting, source revision, requirement/check hashes, retries, descendants, terminal status and human intervention count. Reconcile response IDs after all sessions close, using the shared calculator. Unknown usage remains unknown.

Report three distinct outcomes: the initial generated candidate, the first completed autonomous workflow including internal repairs, and any later human-assisted continuation. Report all-attempt consumption as well as successful-output consumption. Keep hidden evaluation results separate from development gate results. Dollar figures are API list-price equivalents, not subscription charges.

Update `JIRA_BENCHMARK.md`, `QUICKSTART.md`, profile examples and portable packaging for the new verified mode. Publish a new version and preserve historical releases and result directories. Acceptance: a clean extraction runs the deterministic fixture, reproduces statuses and accounting, and preserves the original repository/Jira. Perform model smoke runs only as an explicit development validation step; this roadmap itself starts no run.

## Independent validation and decision rules

First freeze the implementation, public checks, hidden checks, model settings and evaluation protocol. Use a small engineering pilot of six unseen issues across at least two repositories and a mix of default wiring, data mapping, configuration, error paths and multiple entry points. Use three paired repetitions per issue as an initial variability check, with alternating or randomized workflow order. These numbers are a proposed pilot design, not a statistical power claim. Both workflows receive the same public requirements, fixtures, runtime and declared budget; hidden failures cannot trigger a measured repair.

The primary outcome is the fraction of first completed autonomous workflows passing hidden required behavior with zero human intervention. Also report initial-candidate success, refinement counts, regression outcomes, completion latency, all-attempt token/cost totals and cost per independently accepted output. Show failed attempts rather than dropping them from the denominator. Do not count repeated attempts on one issue as additional independent issues.

Use pilot results to estimate variability and choose the larger sample needed for an agreed success-rate margin and meaningful cost difference. Analyze results by issue, accounting for repeated runs and repository clustering. The existing 33 scenarios can provide regression breadth but do not replace realistic unseen integration issues. A later matched Spine-with/without-PKG experiment is needed to isolate PKG's contribution.

Engineering release gate: all mandatory offline tests pass; no known broken fixture is marked complete; immutable checks and resumption protections work; token records reconcile or explicitly identify missing usage. Comparative success is assessed separately: do not declare parity with spec-kit or a universal savings ratio from the six-issue pilot alone.

## First day execution checklist

1. Pin the current Spine development revision and harness baseline; preserve the frozen ONTM-4 evidence and define separate output directories.
2. Write the minimal required-behavior schema and agree which checks are public versus hidden.
3. Build one deterministic integration fixture with default loading and property mapping; verify the controlled broken versions fail.
4. Make missing required checks return unverified/incomplete, and integrate one required command into the native refinement loop.
5. Demonstrate automatic failure → repair → pass with a scripted adapter and confirm every attempt is recorded. Use this as the day-two milestone demo.

The immediate deliverable is a small, testable extension to the existing pipeline. Broader graph features, additional languages, browser/deployment certification and a statistically powered comparison follow after that gate works reliably.
