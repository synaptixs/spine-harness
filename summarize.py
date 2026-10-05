#!/usr/bin/env python3
"""Turn RESULTS_DIR into the comparison tables: per model, per feature, and at fleet scale.

  ./summarize.py                  # prints markdown and writes RESULTS_DIR/summary.md
  ./summarize.py --devs 500,2000  # choose the fleet sizes

Per-feature figures, as in the report:
  * spec-kit: completed runs (see completed(); a Claude run that stalled at spec-kit's own
    "proceed? (yes/no)" question is counted separately);
  * Spine + PKG: codegen run cost + the model's mean intake cost (spine_intake.py);
  * "files outside the ticket": tracked files a run modified. The three stock tickets create new
    code, so any tracked modification is outside the ticket.
Statistics: exact two-sided Mann-Whitney on per-run cost (normal approximation above 200k splits),
a seeded bootstrap 95% interval on the ratio of means, and a sign test over ticket-and-model pairs.
Only python3 is needed; no Spine import.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import random
import statistics as st
from pathlib import Path

RESULTS = Path(os.environ.get("RESULTS_DIR", Path(__file__).resolve().parent / "results")).expanduser()
FEATURES_PER_DEV_YEAR = 48  # 4 a month


def load(pattern: str) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(RESULTS.glob(pattern))]


def completed(d: dict) -> bool:
    """A spec-kit run that got past its own checklist question, as the report counts it.

    Codex runs must actually reach code. Claude Code runs headless cannot be answered mid-step: a run completed when
    its implement step went past the question (more than 3 turns); the rest stalled with no code.
    """
    if d.get("stopped_at_job_cap_before") or any(r.get("exit") or r.get("error") for r in d.get("rows", [])):
        return False
    if "requests" in d["total"] and "turns" not in d["total"]:
        return bool(d.get("reached_code")) and not d.get("paused_for_checklist")
    impl = next((r for r in d["rows"] if r["step"] == "07-implement"), None)
    return bool(impl) and (impl.get("turns") or 0) > 3


def sk_tokens(t: dict) -> int:
    if "cache_read" in t:  # Claude Code reports cache reads separately from input
        return t["input"] + t.get("cache_write", 0) + t["cache_read"] + t["output"]
    return t["input"] + t["output"]  # Codex: input already includes cached tokens


def mw_p(a: list[float], b: list[float]) -> float:
    n, m = len(a), len(b)
    u_obs = sum(x > y for x in a for y in b) + 0.5 * sum(x == y for x in a for y in b)
    mean_u = n * m / 2
    if math.comb(n + m, n) <= 200_000:
        pooled = a + b
        us = []
        for idx in itertools.combinations(range(n + m), n):
            s = set(idx)
            us.append(sum(pooled[i] > pooled[j] for i in s for j in range(n + m) if j not in s))
        return sum(abs(u - mean_u) >= abs(u_obs - mean_u) for u in us) / len(us)
    sd = math.sqrt(n * m * (n + m + 1) / 12)
    z = abs(u_obs - mean_u) / sd
    return math.erfc(z / math.sqrt(2))


def boot(a: list[float], b: list[float], it: int = 20000, seed: int = 7) -> tuple[float, float]:
    rnd = random.Random(seed)
    r = sorted(st.mean(rnd.choices(a, k=len(a))) / st.mean(rnd.choices(b, k=len(b))) for _ in range(it))
    return r[int(0.025 * it)], r[int(0.975 * it)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--devs", default="500,1000,2000,5000,10000")
    fleets = [int(x) for x in ap.parse_args().devs.split(",")]
    models = sorted(p.name for p in RESULTS.iterdir() if p.is_dir() and ((p / "speckit").exists() or (p / "spine").exists()))
    out: list[str] = [f"# spec-kit vs Spine + PKG — results in `{RESULTS}`", "",
        "Codex backend results measure both workflows through Codex, not the original direct API experiment.",
        "Dollar figures are standard short-context API list-price equivalents, not subscription invoices.",
        "A one-ticket pilot is a functional check; its ratios are not a general performance estimate.", ""]
    head = ("| Model | Tool | Runs | Cost / feature | Range | Tokens / feature | Model requests | Wall (min) | "
            "Held-out pass | Repo gate pass | Files outside ticket / run |")
    per_feature = [head, "|" + "---|" * 11]
    stats = ["| Model | Cost gap (95% CI) | Token gap | Runs overlap? | Mann-Whitney p |", "|---|---|---|---|---|"]
    fleet = ["| Model | Tool | " + " | ".join(f"{n:,} devs / yr" for n in fleets) + " |", "|---|---|" + "---|" * len(fleets)]
    pairs: list[float] = []
    spine_missing: list[str] = []
    app_signin = False
    for m in models:
        sk_all = load(f"{m}/speckit/*/summary.json")
        sk = [d for d in sk_all if completed(d)]
        sp_all = load(f"{m}/spine/pass*/*/summary.json")
        sp = [d for d in sp_all if not d.get("aborted") and d.get("usage_complete", True)]
        if len(sp) != len(sp_all):
            out.append(f"_{m}: {len(sp_all)-len(sp)} Spine infrastructure abort(s) excluded from measurements._\n")
        intake = [r for f in sorted((RESULTS / m / "intake").glob("pass*.json")) for r in json.loads(f.read_text())]
        if not sk:
            out.append(f"_{m}: no completed spec-kit implementation; no comparative ratios computed._\n")
            for d in sk_all:
                t = d["total"]
                out.append(f"Spec-kit `{d['ticket']}`: incomplete, {sk_tokens(t):,} recorded tokens, "
                           f"${t['cost_usd']:.6f} API equivalent spent so far.\n")
            for d in sp:
                matching = [r for r in intake if r['ticket'] == d['ticket'] and r['pass'] == d['pass']]
                tokens = d['prompt_tokens'] + d['completion_tokens'] + sum(r['prompt'] + r['completion'] for r in matching)
                cost = d['cost_usd'] + sum(r['cost_usd'] for r in matching)
                out.append(f"Spine `{d['ticket']}`: held-out pass={d.get('held_out_pass')}, "
                           f"repository gate pass={d.get('repo_gate_pass')}; {tokens:,} tokens, "
                           f"${cost:.6f} API equivalent including recorded intake.\n")
            continue
        a = [d["total"]["cost_usd"] for d in sk]
        a_tok = st.mean(sk_tokens(d["total"]) for d in sk)
        a_req = st.mean(d["total"].get("requests") or d["total"].get("turns") or 0 for d in sk)
        a_out = st.mean(len(d["grading"]["tracked_files_modified"]) for d in sk_all)
        a_held = sum(bool(d["grading"]["held_out_pass"]) for d in sk_all)
        stalled = len(sk_all) - len(sk)
        app_signin = app_signin or any(d.get("codex_auth") == "app" for d in sk_all)
        per_feature.append(f"| `{m}` | spec-kit | {len(sk)}" + (f" (+{stalled} stalled)" if stalled else "") +
                           f" | ${st.mean(a):.2f} | ${min(a):.2f}–${max(a):.2f} | {a_tok/1e6:.2f}M | {a_req:.0f} | "
                           f"{st.mean(d['wall_s'] for d in sk)/60:.1f} | {a_held}/{len(sk_all)} | "
                           f"{sum(bool(d['grading'].get('repo_gate_pass')) for d in sk_all)}/{len(sk_all)} | {a_out:.1f} |")
        if not sp:
            # spec-kit alone (e.g. CODEX_AUTH=app with no API key for Spine): no gap to compute here.
            per_feature.append("| | Spine + PKG | not run here | — | — | — | — | — | — | — | — |")
            spine_missing.append(m)
            continue
        i_cost = st.mean(r["cost_usd"] for r in intake) if intake else 0.0
        i_tok = st.mean(r["prompt"] + r["completion"] for r in intake) if intake else 0.0
        i_calls = st.mean(r["calls"] for r in intake) if intake else 0.0
        i_wall = st.mean(r["wall_s"] for r in intake) if intake else 0.0
        b = [d["cost_usd"] + i_cost for d in sp]
        b_tok = st.mean(d["prompt_tokens"] + d["completion_tokens"] for d in sp) + i_tok
        b_req = st.mean(d["calls"] for d in sp) + i_calls
        b_out = st.mean(len(d.get("tracked_files_modified", [])) for d in sp)
        b_held = sum(bool(d.get("held_out_pass")) for d in sp)
        per_feature.append(f"| | Spine + PKG | {len(sp)} | ${st.mean(b):.3f} | ${min(b):.2f}–${max(b):.2f} | "
                           f"{b_tok/1e3:.0f}k | {b_req:.1f} | {(st.mean(d['wall_s'] for d in sp) + i_wall)/60:.1f} | "
                           f"{b_held}/{len(sp)} | {sum(bool(d.get('repo_gate_pass')) for d in sp)}/{len(sp)} | {b_out:.1f} |")
        if min(len(a), len(b)) >= 2 and st.mean(b) > 0:
            lo, hi = boot(a, b)
            stats.append(f"| `{m}` | **{st.mean(a)/st.mean(b):.1f}×** ({lo:.1f}–{hi:.1f}×) | {a_tok/b_tok:.0f}× | "
                         f"{'yes' if min(a) <= max(b) else 'no'} | {mw_p(a, b):.4f} |")
            for label, cost in (("spec-kit", st.mean(a)), ("Spine + PKG", st.mean(b))):
                fleet.append(f"| `{m}` | {label} | " + " | ".join(f"${cost*FEATURES_PER_DEV_YEAR*n:,.0f}" for n in fleets) + " |")
        else:
            out.append(f"_{m}: insufficient repeats for confidence intervals or fleet projections._\n")
        for t in sorted({d["ticket"] for d in sk}):
            ta = [d["total"]["cost_usd"] for d in sk if d["ticket"] == t]
            tb = [d["cost_usd"] + i_cost for d in sp if d["ticket"] == t]
            if ta and tb:
                pairs.append(st.mean(ta) / st.mean(tb))
    out += ["## Per feature", "", *per_feature, ""]
    if spine_missing:
        out.append("Spine + PKG was not run here for " + ", ".join(f"`{m}`" for m in spine_missing) +
                   ", so there is no gap for those models. Compare with the published figures in README.md "
                   "(same tickets, target commit and versions; a different machine and day).\n")
    if app_signin:
        out.append("spec-kit runs marked `codex_auth: app` used a ChatGPT sign-in. Their cost is the API "
                   "list-price equivalent of the tokens Codex recorded, not what the plan was billed.\n")
    out += ["## How big the gap is", "", *stats, ""]
    if len(pairs) >= 2:
        k = sum(r > 1 for r in pairs)
        p = min(1.0, 2 * sum(math.comb(len(pairs), j) for j in range(max(k, len(pairs) - k), len(pairs) + 1)) / 2 ** len(pairs))
        out.append(f"Ticket-and-model pairs: {len(pairs)}; spec-kit dearer in {k}; ratios "
                   f"{min(pairs):.0f}×–{max(pairs):.0f}×; sign test p = {p:.4f}.\n")
    if len(fleet) > 2:
        out += ["## Fleet cost per year (4 features per developer per month)", "", *fleet, ""]
    text = "\n".join(out)
    print(text)
    (RESULTS / "summary.md").write_text(text + "\n")


if __name__ == "__main__":
    main()
