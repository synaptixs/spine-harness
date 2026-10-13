"""Codex response ledger, deduplicated across rollout files (never token_count)."""
from __future__ import annotations

import json
from pathlib import Path

# Standard short-context API list-price equivalents, USD/MTok.
# https://developers.openai.com/api/docs/pricing, retrieved 2026-09-29.
# Deliberately explicit: unknown models fail rather than silently cost $0.
PRICES = {"gpt-5.6-sol": (4.0, 0.4, 5.0, 20.0), "gpt-6-sol": (2.0, 0.2, 2.5, 10.0),
          "gpt-6-astra": (10.0, 1.0, 12.5, 50.0)}
PRICE_BASIS = "Standard short-context API list-price equivalent; not a subscription invoice"


def run_sessions(home: Path, wt: Path | None = None) -> list[Path]:
    files = sorted(home.glob("sessions/**/*.jsonl"))
    if wt is None:
        return files
    keep = []
    for f in files:
        with f.open() as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") == "session_meta":
                    cwd = d.get("payload", {}).get("cwd")
                    if cwd and Path(cwd).resolve() == wt.resolve():
                        keep.append(f)
                    break
    return keep


def records(home: Path, wt: Path | None = None) -> dict[str, dict]:
    found = {}
    for f in run_sessions(home, wt):
        for line in f.read_text().splitlines():
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("type") == "token_usage_record":
                p = d["payload"]
                if not p.get("response_id"):
                    raise ValueError(f"Missing response_id in {f}")
                found[p["response_id"]] = p["usage"]
    return found


def total(records_by_id: dict[str, dict]) -> dict[str, int]:
    keys = {"input": "input_tokens", "cached": "cached_input_tokens",
            "cache_write": "cache_write_input_tokens", "output": "output_tokens",
            "reasoning": "reasoning_output_tokens"}
    return {**{k: sum(u.get(field, 0) or 0 for u in records_by_id.values())
               for k, field in keys.items()}, "requests": len(records_by_id)}


def session_usage(home: Path, wt: Path | None = None) -> dict[str, int]:
    return total(records(home, wt))


def cost(model: str, u: dict) -> float:
    pi, pr, pw, po = PRICES[model]
    plain = max(u["input"] - u["cached"] - u["cache_write"], 0)
    return (plain*pi + u["cached"]*pr + u["cache_write"]*pw + u["output"]*po)/1e6


def rates(model: str) -> tuple[float, float, float, float]:
    pi, pr, pw, po = PRICES[model]
    return pi/1e6, po/1e6, pr/1e6, pw/1e6
