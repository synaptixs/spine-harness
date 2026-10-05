"""Spine's intake cost — the step the codegen benchmark skips, because it starts from a ready spec.

Usage: python spine_intake.py <model> <pass_no> [--dry-run]

Feeds each ticket, in the same words spec-kit received, to Spine's real file-source intake
(`build_service_for("file://…")`, dry run, nothing written to any tracker) and records every model
call it makes. The per-feature Spine + PKG cost in the report is codegen + this.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import harness_config as C

ap = argparse.ArgumentParser()
ap.add_argument("model"); ap.add_argument("pass_no", type=int); ap.add_argument("--dry-run", action="store_true")
A = ap.parse_args()
OUT = C.RESULTS_DIR / A.model / "intake"
if A.dry_run:
    print(f"[dry-run] intake on {A.model} for {C.TICKETS} → {OUT / f'pass{A.pass_no}.json'}")
    sys.exit(0)

C.use_tree(C.SPINE_CODE_DIR)
if C.SPINE_BACKEND == "codex":
    os.environ["CODEX_CALLS_DIR"] = str(OUT / f"pass{A.pass_no}-calls")
    from codex_llm import install
    install()
elif A.model.startswith("gpt-6"):
    sys.path.insert(0, str(C.HERE))
    import gpt6_shim  # noqa: F401,E402
os.environ["ORCHESTRATOR_INTAKE_MODEL"] = A.model

import codegen_benchmark as cb  # noqa: E402
import heldout_fix
heldout_fix.apply(cb)
CUSTOM_CATALOG = C.configure_tickets(cb)
from scenario_catalog import fingerprint
SCENARIO_FINGERPRINT = fingerprint(cb.TICKETS)
from orchestrator.core.llm import litellm_client as lc  # noqa: E402
from orchestrator.intake.factory import build_service_for  # noqa: E402
from orchestrator.intake.service import parse_source_uri  # noqa: E402

calls: list[dict] = []
_complete = lc.LiteLLMClient.complete


async def recording_complete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    r = await _complete(self, *args, **kwargs)
    calls.append({"model": r.model, "prompt": r.prompt_tokens, "completion": r.completion_tokens,
                  "cost_usd": r.cost_usd})
    return r


lc.LiteLLMClient.complete = recording_complete  # type: ignore[method-assign]


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for key in C.TICKETS:
        t = next(t for t in cb.TICKETS if t.key == key)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / f"{key}.md"
            f.write_text(C.ticket_text(t, heading=True))
            uri = f"file://{f}"
            calls.clear()
            t0 = time.time()
            svc = build_service_for(uri, dry_run=True)
            plan = await svc.analyze(parse_source_uri(uri)[1])
            if not calls or not plan.specs:
                raise RuntimeError(f"Intake did not produce a measured feature spec for {key}")
            results.append({"ticket": key, "pass": A.pass_no, "model": A.model,
                            "backend": C.SPINE_BACKEND, "codex_auth": C.CODEX_AUTH,
                            "scenario_fingerprint": SCENARIO_FINGERPRINT, "custom_catalog": CUSTOM_CATALOG,
                            "wall_s": round(time.time() - t0, 1),
                            "calls": len(calls), "prompt": sum(c["prompt"] for c in calls),
                            "completion": sum(c["completion"] for c in calls),
                            "cost_usd": round(sum(c["cost_usd"] for c in calls), 6),
                            "specs": len(plan.specs), "intents": len(plan.intents)})
            print(json.dumps(results[-1]), flush=True)
    (OUT / f"pass{A.pass_no}.json").write_text(json.dumps(results, indent=2))


asyncio.run(main())
