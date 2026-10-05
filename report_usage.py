#!/usr/bin/env python3
"""Count exported Codex response ledgers without credentials or personal tooling.

Run only after child processes close. Counts saved benchmark-arm sessions, including
failed attempts whose ledgers were exported; unrecorded usage remains unknown.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from codex_usage import PRICE_BASIS, PRICES, cost, total

PATTERNS = ("*/speckit/*/session-rollout-*.jsonl",
            "*/spine/pass*/codex-calls/*/rollout-*.jsonl",
            "*/intake/pass*-calls/*/rollout-*.jsonl")


def summarize_usage(root: Path) -> dict:
    responses: dict[str, tuple[str, dict]] = {}
    files = sorted({p for pattern in PATTERNS for p in root.glob(pattern)})
    for file in files:
        model = None
        for line in file.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            payload = row.get("payload", {})
            if row.get("type") == "turn_context":
                model = payload.get("model")
            if row.get("type") == "token_usage_record":
                response_id = payload.get("response_id")
                if not model or not response_id:
                    raise ValueError(f"Missing model or response ID: {file}")
                record = (model, payload["usage"])
                if response_id in responses and responses[response_id] != record:
                    raise ValueError(f"Conflicting usage for response {response_id}")
                responses[response_id] = record
    portable = root / 'response-ledger.json'
    if not files and portable.exists():
        for item in json.loads(portable.read_text())['responses']:
            response_id = item['response_id']
            record = (item['model'], item['usage'])
            if not response_id or not item['model']:
                raise ValueError('Portable ledger has a missing model or response ID')
            if response_id in responses and responses[response_id] != record:
                raise ValueError(f'Conflicting portable usage for response {response_id}')
            responses[response_id] = record
    models = {}
    for model in sorted({m for m, _ in responses.values()}):
        usage = total({rid: u for rid, (m, u) in responses.items() if m == model})
        models[model] = {**usage, "tokens": usage["input"] + usage["output"],
                         "uncached_input": max(0, usage["input"] - usage["cached"] - usage["cache_write"]),
                         "cost_usd": cost(model, usage) if model in PRICES else None}
    return {"tool": "Codex", "price_basis": PRICE_BASIS,
            "scope": "Exported benchmark-arm sessions only; excludes diagnostics and missing/unexported records",
            "usage_completeness": "Not inferred from tokens; inspect run summaries, usage.json and failure logs",
            "session_files": len(files),
            "ledger_source": "raw session exports" if files else "portable response ledger" if portable.exists() else "none",
            "models": models}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    if not args.results.is_dir():
        parser.error("--results must be an existing results directory")
    result = summarize_usage(args.results)
    print(json.dumps(result, indent=2))
    if not result["models"]:
        raise SystemExit("No exported per-response Codex ledgers found; usage is unknown, not zero")


if __name__ == "__main__":
    main()
