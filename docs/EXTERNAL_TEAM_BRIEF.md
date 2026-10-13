# Spine Harness: external team briefing

**Purpose:** Explain what Spine Harness measures, how a valid comparison is run, what evidence it produces, and where additional tools or benchmarks could fit.

**Status snapshot:** 13 October 2026, based on [Spine Harness source revision `d36142c`](https://github.com/synaptixs/spine-harness/tree/d36142c9f443ea6553cc7761c695563e5f135762). Roadmap items below are proposals, not shipped features. This page is designed to stand alone when copied to Confluence.

## Executive summary

Spine Harness is an experiment runner for comparing **specification-to-code workflows** on the same software issue. Its current four-workflow pilot runs **Spine + PKG**, **Spine + integrated OpenSpec + PKG**, **standalone OpenSpec**, and **Spec Kit**. Each workflow receives the same saved task, pre-fix application commit, model and reasoning setting, and independently selected checks. It works in its own disposable clone and produces a patch and auditable result. Repeat that one-issue protocol across issues and repositories, then aggregate compatible closed runs. See the [project overview](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/README.md) and [framework reference](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/FRAMEWORK_MATRIX.md).

The harness answers questions such as: *Did a workflow complete? Did its patch pass the selected independent behavior checks? What did it cost in recorded tokens and time? Where did it stop?* A single issue does not establish that one workflow is generally better. A completed workflow, Spine's native validation, and independent acceptance are **separate outcomes**.

**Recommendation:** Keep the current four-arm pilot as the qualification path. Add new tools through measured, versioned adapters. Explore [DeepSWE](https://deepswe.datacurve.ai/) through a small Python-task feasibility study using its own pristine verifier; do not treat the current SWE-bench export or local test result as a DeepSWE score.

## Terms and the four current workflows

| Term | Meaning in this guide |
| --- | --- |
| **Task** | One saved GitHub/Jira issue, local `id`/`title`/`description` snapshot, or supported SWE-bench instance. |
| **Baseline** | The committed application revision before the requested fix. |
| **Arm** | One workflow's isolated attempt on that same task and baseline. |
| **PKG** | Spine's Product Knowledge Graph, used to ground its native feature workflow in repository structure. |
| **Independent acceptance** | Operator-supplied checks kept outside the model's worktree and run after generation; they must expose the missing behavior on the pre-fix baseline. |

| Arm | What differs | Tool source |
| --- | --- | --- |
| **Spine + PKG** (`spine-pkg`) | Native Spine feature flow grounded by PKG, without OpenSpec intake. | Bundled Spine `v3.57.1`. |
| **Spine + integrated OpenSpec + PKG** (`spine-openspec`) | Native Spine feature flow uses its **built-in** OpenSpec intake as well as PKG. | The same bundled Spine revision; it does not call the standalone OpenSpec CLI. |
| **OpenSpec** (`openspec`) | Standalone OpenSpec creates the specification context and drives implementation. | Current npm release resolved at setup, then pinned for the attempt. |
| **Spec Kit** (`speckit`) | Standalone Spec Kit's specify, plan, tasks, and implement sequence. | Current stable Git tag resolved at setup, then pinned to a commit. |

All four built-in arms use the **same configured Codex model and reasoning effort**. They can make different numbers of model calls because their native workflows differ. Tool setup freezes the standalone versions; PKG and integrated OpenSpec ship inside the pinned Spine checkout. The example configuration runs the arms in the order shown above. Details: [one-issue quick start](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/MATRIX_QUICKSTART.md).

## How one comparison works

```text
Saved issue + pre-fix commit + common model settings + independent checks
                                  |
                     tool setup -> doctor -> prepare
                                             |
                        four isolated workflow attempts
                                             |
                      post-run checks + patch/usage capture
                                             |
                    report + evidence package -> multi-task study
```

| Stage | Operator or harness action | Evidence and stop condition |
| --- | --- | --- |
| **1. Choose and freeze** | Select one issue, a full pre-fix commit, applicable repository dependencies, regression commands, independent acceptance, and any owner-approved scope answers. | The issue must be understandable and the baseline must contain its prerequisites. Keep one shared task text for every arm. |
| **2. Resolve tools and diagnose** | Freeze standalone Spec Kit/OpenSpec versions; check CLI login, pinned Spine checkout, application interpreter, paths, and sandbox. `doctor` makes no model call unless the optional, separately authorized smoke is requested; tool resolution or download can still use the network. | Version and environment failures stop before measurement. |
| **3. Prepare** | Create a common disposable baseline, normalize the issue, hash protected inputs, and verify that regression passes and acceptance fails for the target behavior. Check a known fix when available. | `PREPARED.json`, `TASK.json`, baseline diagnostics, and frozen checks. An unrelated failure makes the task unsuitable. No model call occurs here. |
| **4. Run** | After authorization, run each workflow in its own clone. Capture specs, code changes, model stages, native Spine status, logs, and response usage. | A setup or measurement defect marks the attempt invalid; a genuine workflow failure under a valid setup remains a result. Do not silently rerun or repair one arm. |
| **5. Check and report** | Run the same independent regression/acceptance commands against each generated patch; verify protected tests and original source stayed unchanged. | Per-arm `RESULT.json`, `COMPARISON_REPORT.md`/`.html`, `RESULTS.json`, usage and integrity evidence, and patches. |
| **6. Package and aggregate** | Package a closed, valid task result and combine compatible task directories across repositories. | `comparison-results.zip` for a task; `MATRIX_STUDY_REPORT.md`/`.html` and `MATRIX_STUDY_RESULTS.json` for a study. |

This is the current [framework-matrix protocol](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/FRAMEWORK_MATRIX.md), not an automatic issue-to-merged-PR service. The original application checkout and issue tracker are read-only during measurement; proposed code is retained as patches.

### Reading a result correctly

| Signal | Meaning | What it does **not** mean |
| --- | --- | --- |
| Workflow completed | The arm reached the end of its configured workflow. | Its patch is correct. |
| Native Spine validation | Spine's own feature/judge/required-behavior gates ran and reported an outcome. | An independent evaluator agreed. |
| Regression and independent acceptance | The selected frozen commands passed on the generated patch, and protected inputs were unchanged. | Every possible requirement is satisfied. |
| Recorded tokens and cost | Closed response records support a token total and **API list-price equivalent** estimate. | A subscription invoice or a zero cost for missing usage. |
| Wall time | Observed workflow and total elapsed time, separately recorded. | Pure model inference latency. |
| Invalid attempt | A setup, source-integrity, timing, or measurement defect prevents a fair comparison. | A model or framework failure. |

Missing usage is reported as **unknown**. The results archive can contain issue text and generated source; its credential-pattern scan is not a general confidentiality filter. Teams must review exports and use approved storage for private tasks. The [reporting contract and limits](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/FRAMEWORK_MATRIX.md#what-the-results-measure) describe the exact fields.

## Current study modes and maturity

| Mode | Current use | Boundary |
| --- | --- | --- |
| **One-issue four-arm matrix** | Qualify one Python application issue across all four built-in workflows; repeat with fresh configs for more issues. | The main path for external teams. One attempt is diagnostic. |
| **Multi-task aggregation** | Combine compatible, closed results from multiple issues or repositories. | Rejects mismatched task type, model/settings, tool versions, pass counts, and invalid evidence. Related issues in one repository are not independent projects. |
| **33-scenario reference matrix** | Schedule 33 catalog tasks across four arms (132 measurements per pass). | A larger study; no completed full four-arm 132-measurement run is claimed in the current validation notes. |
| **Matched context comparison** | Give one common implementation step four separately prepared framework contexts. | An implementation-only protocol; context creation cost is outside that comparison and results must not be pooled with full-workflow results. |
| **Historical two-arm Jira runner** | Reproduce earlier Spec Kit versus Spine + PKG work. | Different protocol and reports; keep its results separate. |
| **Official SWE-bench path** | Export arm patches as official prediction JSONL and invoke the official evaluator explicitly. | Its four-arm end-to-end official evaluation has not yet been validated. Local checks are not an official resolved verdict. |

The latest [v21 handover validation](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/releases/RELEASE_VALIDATION_V21.md) covers offline tests and package integrity, **not** a new model benchmark. A prior public issue produced four report rows, but the Spine-integrated OpenSpec arm stopped at a native scope-clarity question; a later isolated run passed selected checks while Spine's native judge still rejected that generated patch. Those outcomes are documented in the [pilot guide](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/MATRIX_QUICKSTART.md#previous-pilot-evidence). They are useful diagnostic evidence, not a clean all-four success claim.

The current native feature adapter uses a prepared **Python** application interpreter and checks. A Windows/WSL2 package exists, but its four-arm path has not been live-validated on a recipient machine; the current four-arm `doctor` explicitly checks for macOS tools. Non-Python applications and container-based benchmark environments require reviewed execution adapters before a correctness comparison. See the [platform notes](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/FRAMEWORK_MATRIX.md#multiple-application-repositories) and [release record](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/releases/RELEASE_VALIDATION_V21.md).

## How an external team can start

1. Read the [macOS package quick start](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/portable/macos/QUICKSTART.md) and [full qualification guide](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/MATRIX_QUICKSTART.md). Use one authorized Python repository and one clear issue first.
2. Copy the [example four-arm configuration](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/examples/framework-matrix.example.json). Supply a full pre-fix SHA, saved task JSON, application interpreter, regression commands, and independent acceptance commands. The example values are placeholders, not a runnable test case.
3. Resolve tools, run `doctor` and `prepare`, then inspect the frozen baseline and failure evidence. The issue must be unsolved at that baseline; independent acceptance must fail for the intended behavior rather than for missing dependencies. Check a known fix if available.
4. Authorize the specific model run and data transfer, then run once. Review each arm's separate workflow, native, regression, and acceptance status. Package the closed result only when the protocol is valid.
5. Repeat with fresh names and paths for additional issues. Aggregate only compatible closed results, keeping public and private task populations separate.

Setup and preparation do not launch the four paid arms. The optional doctor model smoke and `run --approved` do consume model tokens. Instructions and exact commands live in the linked quick start; this briefing does not replace its preflight.

## Adding more tools: proposed roadmap

The harness already supports an [external command adapter](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/FRAMEWORK_MATRIX.md#inputs-and-preparation): an argv command receives the disposable repository, frozen task, output directory, model, and login home. It may emit a response-level usage ledger. That is an integration seam, **not** proof that any candidate tool is installed, comparable, or supported today.

| Sequence | Candidate work | Completion evidence before wider use |
| --- | --- | --- |
| **1. Harden qualification** | Keep a small set of clearly scoped tasks with a pre-fix baseline, passing regression, failing independent acceptance, and a known fix where possible. Make platform and dependency checks match the actual runtime. | Offline preflight stops defective tasks before model calls; one end-to-end attempt produces a complete, interpretable report without manual repair. |
| **2. Add one tool at a time** | Wrap a candidate through the external adapter, pin its version, define its model-visible context, and record every response or mark usage unknown. | Same task/baseline/model/checks as existing arms; isolated output, protected tests, reproducible setup, and a reviewable failure path. |
| **3. Evaluate Graphify and codebase memory** | If Graphify supplies graph views or code context, test it as an explicit context variant beside the current PKG arm. For codebase memory, key any cache to source revision and inputs and prevent answers from one attempt leaking into another. | A written hypothesis, frozen artifacts, and matched comparisons establish whether retrieval quality or selected acceptance changes. Neither candidate is currently a built-in arm. |
| **4. Expand execution environments** | Add language-specific application setup, test confinement, and patch handling for a chosen non-Python stack or container benchmark. | Baseline failure and known-fix success in the real isolated environment, then one valid four-arm pilot. |
| **5. Scale studies and reporting** | Add more independent tasks/repositories and repeated attempts; retain repository-level grouping, uncertainty, missing-usage denominators, and explicit protocol versions. | Results remain comparable and a reported difference can be traced to task, tool revision, model settings, and verifier evidence. |

Two related ideas should have separate protocols. **PKG question answering** would measure retrieval and answer grounding against a fixed question set; it is not a code-generation arm. **Model/provider or reasoning-level comparisons** change the model protocol; first keep the four workflow contexts fixed, then run a separately labeled model study. This avoids attributing a model change to Graphify, memory, or PKG.

## DeepSWE: fit and integration proposal

[DeepSWE](https://deepswe.datacurve.ai/) is DataCurve's public long-horizon software-engineering benchmark. It is a **task and evaluation source, not a fifth framework arm**. Its [repository](https://github.com/datacurve-ai/deep-swe/blob/main/README.md) describes **113 original tasks across TypeScript, Go, Python, JavaScript, and Rust**. Each task uses a Harbor-style `task.toml`, `instruction.md`, environment Dockerfile, verifier tests, and a reference solution. DeepSWE v1.1 grades an agent's committed patch in a **separate pristine verifier environment** and emits structured reward and test reports. [Pier](https://github.com/datacurve-ai/pier) runs the tasks in Docker or Modal; the public DeepSWE leaderboard reports Pier runs using `mini-swe-agent`.

**Why it makes sense:** DeepSWE would add independently authored, longer tasks and a behavior-focused verifier to our current issue studies. It can test whether framework context helps on harder repository changes, provided every arm sees the same instruction and base image and the official verifier stays outside the model-visible workspace. This is an inference about fit, not a validated Spine Harness integration.

**Why it is a separate project:** Spine Harness currently starts from a local Git baseline and a prepared Python interpreter. DeepSWE supplies a Harbor/Pier container task, several non-Python languages, and a verifier that collects committed changes into a clean container. The harness's `evaluate-swebench` command is wired to the **SWE-bench** evaluator and cannot score a DeepSWE task. A local `pytest` pass, a successful arm exit, or a patch export must not be labeled a DeepSWE reward. DeepSWE's published leaderboard also uses a different agent protocol, so a four-arm harness study should not be compared directly with its model leaderboard numbers. [DeepSWE task and grading contract](https://github.com/datacurve-ai/deep-swe/blob/main/README.md); [current harness SWE-bench boundary](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/FRAMEWORK_MATRIX.md#official-swe-bench-evaluation).

This needs task, runtime, verifier, and result-schema work; it is more than adding another `frameworks` entry. It should follow a clean one-issue harness qualification before any paid DeepSWE attempt.

### Suggested feasibility gates

| Gate | What to prove before moving on |
| --- | --- |
| **A. Offline task audit** | Pin the DeepSWE dataset revision and Pier version. Select one or two **Python** tasks with suitable owning code. Confirm task image, baseline commit, instruction, resource limits, verifier inputs, and applicable upstream licenses. DeepSWE's [provenance notice](https://github.com/datacurve-ai/deep-swe/blob/main/PROVENANCE.md) says its Apache-2.0 license does not relicense upstream projects. |
| **B. Verifier calibration** | In the actual container path, show that the pristine baseline fails for the intended behavior and the supplied reference solution passes. Keep `tests/` and `solution/` inaccessible to the model during the attempt. If that cannot be demonstrated, stop before model calls. |
| **C. One-arm adapter spike** | Determine whether a Spine Harness arm should run as a Pier agent wrapper or whether its patch can be submitted through an equivalent official verifier path. Preserve DeepSWE's collection/commit semantics and record task ID, image digest, tool/model pins, logs, and full cost evidence. Do not assume an adapter API exists until tested. |
| **D. Matched four-arm pilot** | Run all four arms on the same eligible task, with the same model settings and independent verifier. Record both harness workflow outcomes and DeepSWE `reward.json`/test evidence separately. A setup defect invalidates the matched attempt; a genuine arm failure stays visible. |
| **E. Expand only after validation** | Add more Python tasks and repeated attempts; then design language-specific adapters for TypeScript, Go, JavaScript, or Rust. Report task selection and the denominator. Use “DeepSWE task study” unless the run reproduces the publisher's exact benchmark and reporting protocol. |

No DeepSWE task or model call has been run by Spine Harness as of this snapshot. This proposal is for feasibility work, not a claimed benchmark result.

## Responsibilities and decision points

| Role | Supplies or approves |
| --- | --- |
| Application/task owner | The issue's intended behavior, pre-fix revision, scope answers, and authorized repository access. |
| Benchmark operator | Reproducible dependencies, common task text, tool/model pins, independent checks, preflight review, and an explicit model-spending attempt. |
| Harness | Isolation, freezing/hashing, per-arm execution, evidence capture, integrity checks, honest failure and unknown-usage reporting. |
| Evaluator/reviewer | Interpretation of selected checks, external verifier reports, task sampling, uncertainty, and limits on any comparative claim. |

For private repositories, obtain the organization's approval for model/data use, keep credentials outside configs and archives, and review result bundles before sharing. A Confluence summary can link to an approved evidence location; it should not paste raw private issue text, source patches, or credentials into a broadly accessible page.

## Source links and next reading

- [Spine Harness repository and four-arm overview](https://github.com/synaptixs/spine-harness/tree/d36142c9f443ea6553cc7761c695563e5f135762)
- [One-issue qualification guide](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/MATRIX_QUICKSTART.md)
- [Framework configuration, result fields, adapters, and SWE-bench boundary](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/FRAMEWORK_MATRIX.md)
- [33-scenario reference study](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/REFERENCE_MATRIX.md) and [matched context comparison](https://github.com/synaptixs/spine-harness/blob/d36142c9f443ea6553cc7761c695563e5f135762/docs/CONTEXT_MATRIX.md)
- [DeepSWE project](https://deepswe.datacurve.ai/), [task and verifier format](https://github.com/datacurve-ai/deep-swe/blob/main/README.md), [upstream code provenance](https://github.com/datacurve-ai/deep-swe/blob/main/PROVENANCE.md), and [Pier runner](https://github.com/datacurve-ai/pier)
