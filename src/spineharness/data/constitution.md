<!--
Sync Impact Report
- Version change: (unratified placeholder template) → 1.0.0
- Modified principles: none (initial ratification; all eight principles are new)
- Added sections:
  - Core Principles I–VIII (derived from CLAUDE.md's "Invariants — break these and things
    get subtly wrong")
  - Naming & Documentation Discipline (derived from CLAUDE.md preamble + docs/specs rules)
  - Quality Gate & Workflow (derived from CONTRIBUTING.md's gate, branch, and episteme rules)
  - Governance (amendment procedure + versioning policy)
- Removed sections: none (all template placeholders replaced)
- Templates requiring updates: none — this command does not modify dependent templates;
  `.specify/templates/plan-template.md` and other consumers read this file at runtime.
- Follow-up TODOs:
  - TODO(RATIFICATION_DATE): the prior constitution file was an unfilled placeholder
    scaffold, so no original adoption date exists in repo history. Set this to the actual
    date this version is formally adopted, if different from Last Amended.
-->

# Spine Constitution

## Core Principles

### I. The PKG Is the Source of Truth
Comprehension surfaces (`understand`, `state`, `overview`, renderers) MUST render facts
already present in the Product Knowledge Graph. They MUST NOT re-derive facts from paths,
filenames, or other heuristics at render time. A new fact starts in `pkg/facts.py` and the
relevant extractor front-end — never in a renderer.

Rationale: the PKG is the one place facts are asserted; letting renderers infer their own
facts creates two sources of truth that silently diverge.

### II. Deterministic, No-LLM Comprehension
`understand` and `state` MUST be deterministic: the same code input MUST produce the same
output every time. These paths MUST NOT call an LLM, use randomness, or read a timestamp.

Rationale: determinism is what makes `episteme/` trustworthy as a diffable knowledge base
and safe to gate CI on. A single nondeterministic input would make every diff suspect.

### III. Deterministic, Seeded Layout
Any visual surface MUST precompute positions deterministically (seeded, in Python) rather
than using a random or force-directed layout. Only the reveal may animate — never the
layout or the underlying data.

Rationale: a picture that redraws differently for an identical commit cannot be diffed or
trusted in review.

### IV. Zero-Build Web UI
The operator web UI (`registry/api/web/`) MUST remain vanilla JS: zero npm, no
`node_modules`, no template engine, no bundler, and no d3/cytoscape-class dependency.
CSS/JS ship as real files under `web/static/`, served at `/static`.

Rationale: this is a deliberate, stated choice (see the preamble of
`registry/api/web/shell.py`), trading library convenience for an operator surface anyone can
read and modify without a toolchain.

### V. Self-Contained Shared Artifacts
Anything meant to leave the building — reports, exports — MUST inline its CSS/SVG and fetch
nothing external at view time.

Rationale: `page_shell()` links `/static`, so a saved copy of a served page loses its
styling; an artifact that only renders correctly inside this app's server is not shareable.

### VI. Group by Owning Module, Never by Symbol ID
Aggregations MUST group nodes by their owning module's name/path — resolved by walking
`CONTAINS` upward, falling back to `provenance.file` — and MUST NOT group by raw symbol id.

Rationale: some language ids are symbols, not locations (e.g. `cpp:HSL2RGB`); grouping by id
makes every function its own component and floods any layout built on top of it.

### VII. Bound Honestly
Aggregations MUST cap their output and MUST record what was elided (e.g. `build_overview`'s
`truncated{}`). Present results as "top N of M"; never let a clipped view imply
completeness.

Rationale: an unbounded aggregation is a performance and readability hazard, but a silently
bounded one is worse — it looks complete when it isn't.

### VIII. Commit-Keyed, Clean-Tree Caching
Caches (`pkg/persistence.py`) are commit-keyed and MUST only be trusted when the working
tree is clean.

Rationale: a cache keyed only on commit hash is wrong the moment uncommitted changes exist;
trusting it against a dirty tree reintroduces exactly the staleness the cache was meant to
avoid.

## Naming & Documentation Discipline

- The product is **Spine**; the package, import, and CLI stay `orchestrator` (PyPI:
  `synaptixs-spine`). Use "Spine" in prose and docs, `orchestrator` in commands.
- The knowledge base directory is **`episteme/`** (previously `memory-bank/`), but the
  published identifiers that predate the rename — `read_memory_bank` (MCP),
  `GET /v1/capabilities/memory-bank`, `ORCHESTRATOR_MEMORY_BANK_DIR`, `memory_bank_dir()`,
  and the `memory-bank/` SDLC artifact-key prefix — are contracts and MUST NOT be renamed
  casually. Resolve the directory via `understand.BANK_DIRNAME` / `memory_bank_dir()`
  (writes) or `existing_bank_dir()` (reads), never a literal path.
- Design records live in `docs/specs/` and stay tracked on purpose: `understand` ingests
  markdown from disk whether or not git tracks it, so an untracked docs tree makes
  `episteme/` describe `Doc` nodes CI cannot see, and `understand --check` fails on a diff
  that cannot be reproduced. Never delete a tracked doc to "tidy up," and never leave an
  untracked markdown tree inside the checkout.
- New plans and new design records go **outside** the checkout (ruled 2026-09-16). Point the
  currency gate at them instead of adding them to `docs/specs/`:
  `python scripts/roadmap-status.py --check <path-to-plan>`.

## Quality Gate & Workflow

- Before pushing, the gate MUST be green locally: `mypy src tests` (not just `src`) and
  `ruff format --check .`. Changing a `Protocol` requires updating its test fakes — typing
  `src` alone passes locally and fails CI.
- CI additionally runs the generated-artifact `--check` gates (architecture and knowledge
  foundation SVGs, MCP tool inventory, matrix count, state numbers, `pkg accuracy --check`),
  `sdlc_shapes.py`, `pkg verify`, `orchestrator understand .`, and the test suite. If a
  version bump touches any of the checked artifacts, re-run all of them together.
- Work happens on branches cut from `develop`; `main` only moves through a
  `develop` → `main` release promotion PR requiring a code-owner review and a passing
  security scan. Never commit directly to `main`.
- `episteme/` MUST NOT be committed by a contributor branch. It is regenerated after merge
  by the episteme workflow, keyed to the merge ref — a branch cannot keep it current, and
  only a rebase (never a re-run) clears a staleness failure caused by another merge landing
  first. The one exemption is the release promotion PR itself.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).

## Governance

This constitution's principles and gates supersede ad hoc practice for the areas they
cover; `CLAUDE.md`, `AGENT_GUIDE.md`, `CONTRIBUTING.md`, and `OPERATIONS.md` remain the
detailed runtime guidance this document summarizes and does not replace.

Amendments proceed by: proposing the change and its rationale, updating this document, and
bumping the version per semantic versioning — MAJOR for a backward-incompatible removal or
redefinition of a principle, MINOR for a new principle or materially expanded guidance,
PATCH for wording or clarification with no semantic change. Update `Last Amended` to the
date of the change.

Reviewers verify compliance with these principles where relevant to a change under review;
a deviation must be justified in the PR description, not silently merged.

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): original adoption date unknown | **Last Amended**: 2026-09-25
