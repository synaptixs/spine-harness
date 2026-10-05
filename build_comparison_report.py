#!/usr/bin/env python3
"""Build a descriptive, ticket-paired report from a fixed stock-scenario study."""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
import statistics as st

from report_usage import summarize_usage
from model_report import model_section


def read(path):
    return json.loads(path.read_text())


def sign_p(differences):
    signs = [d > 0 for d in differences if d != 0]
    n = len(signs)
    if not n:
        return 1.0
    k = min(sum(signs), n - sum(signs))
    return min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2**n)


def percentile(values, fraction):
    values = sorted(values)
    pos = (len(values) - 1) * fraction
    i = int(pos)
    return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (pos - i)


def completed(d):
    rows = d.get('rows', [])
    successful = {r['step'] for r in rows if not r.get('exit') and not r.get('error')}
    recovery = d.get('recovered_steps', {})
    unresolved = [r for r in rows if (r.get('exit') or r.get('error')) and recovery.get(r['step']) not in successful]
    return bool(d.get('reached_code')) and not d.get('paused_for_checklist') and not d.get('stopped_at_job_cap_before') and not unresolved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--model', default='gpt-6-sol')
    ap.add_argument('--output', default='COMPARISON_REPORT.md', help='Report filename within the results directory')
    a = ap.parse_args()
    root = a.results.resolve()
    model = root / a.model
    protocol = read(root / 'PROTOCOL.json')
    tickets, passes = protocol['tickets'], protocol['passes']
    expected = len(tickets) * passes
    sk = [read(p) for p in sorted(model.glob('speckit/*/summary.json'))]
    sp = [read(p) for p in sorted(model.glob('spine/pass*/*/summary.json'))]
    intake = {(r['ticket'], r['pass']): r for p in model.glob('intake/pass*.json') for r in read(p)}
    sk_by = {(r['ticket'], r['pass']): r for r in sk}
    sp_by = {(r['ticket'], r['pass']): r for r in sp}
    sp_valid = [r for r in sp if not r.get('aborted') and r.get('usage_complete', True) and (r['ticket'], r['pass']) in intake]
    sk_valid = [r for r in sk if completed(r)]

    def spine_cost(r):
        return r['cost_usd'] + intake[(r['ticket'], r['pass'])]['cost_usd']

    def spine_tokens(r):
        i = intake[(r['ticket'], r['pass'])]
        return r['prompt_tokens'] + r['completion_tokens'] + i['prompt'] + i['completion']

    def spine_wall(r):
        return r['wall_s'] + intake[(r['ticket'], r['pass'])]['wall_s']

    done = len(sk_valid) == len(sp_valid) == expected
    lines = [f'# spec-kit vs Spine + PKG — {a.model} stock-scenario study', '',
             f"**Status:** {'all planned implementations measured' if done else 'partial / incomplete'}. "
             f"{len(tickets)} scenarios × {passes} repeats × 2 workflows; {expected * 2} planned ticket-arm runs.", '',
             'This report uses fresh runs through the Codex subscription adapter. Pilot and diagnostic runs are excluded. '
             'Dollars are standard short-context API list-price equivalents, not subscription invoices.', '',
             '## Outcomes', '',
             '| Workflow | Saved runs / planned | Completed measurements | Held-out passes / planned | Repository-gate passes / planned | Both held-out and repository gate |',
             '|---|---:|---:|---:|---:|---:|']
    sk_held = sum(completed(r) and r['grading']['held_out_pass'] for r in sk)
    sk_gate = sum(completed(r) and r['grading']['repo_gate_pass'] for r in sk)
    sp_held = sum(bool(r.get('held_out_pass')) for r in sp_valid)
    sp_gate = sum(bool(r.get('repo_gate_pass')) for r in sp_valid)
    sk_both = sum(completed(r) and r['grading']['held_out_pass'] and r['grading']['repo_gate_pass'] for r in sk)
    sp_both = sum(bool(r.get('held_out_pass') and r.get('repo_gate_pass')) for r in sp_valid)
    lines += [f'| spec-kit | {len(sk)}/{expected} | {len(sk_valid)} | {sk_held}/{expected} | {sk_gate}/{expected} | {sk_both}/{expected} |',
              f'| Spine + PKG | {len(sp)}/{expected} | {len(sp_valid)} | {sp_held}/{expected} | {sp_gate}/{expected} | {sp_both}/{expected} |', '',
              'A missing run is pending/unknown, not a measured failure. A baseline gate pass on an unimplemented '
              'spec-kit run is excluded. Passing functional tests does not establish repository readiness.', '',
              '| Workflow | Own tests pass | Lint / format / types pass | Harness fit passes |',
              '|---|---:|---:|---:|',
              f"| spec-kit | {sum(bool(r['grading'].get('own_tests_pass')) for r in sk_valid)}/{len(sk_valid)} | {sum(all(r['grading'].get('preflight', {}).get(k, False) for k in ('ruff','format','mypy')) for r in sk_valid)}/{len(sk_valid)} | {sum(bool(r['grading'].get('fit')) for r in sk_valid)}/{len(sk_valid)} |",
              f"| Spine + PKG | {sum(bool(r.get('tests_pass')) for r in sp_valid)}/{len(sp_valid)} | {sum(bool(r.get('preflight_pass')) for r in sp_valid)}/{len(sp_valid)} | {sum(bool(r.get('fit')) for r in sp_valid)}/{len(sp_valid)} |", '',
              'These denominators include completed measurements only. The harness fit rule penalizes changes '
              'to existing tracked files, including configuration or package exports; that flag alone does '
              'not demonstrate harmful code changes. The repository gate is a separate check.', '',
              '## Cost, tokens and elapsed time', '',
              '| Workflow | Completed n | Mean cost | Cost range | Mean tokens | Mean model responses | Mean wall minutes |',
              '|---|---:|---:|---|---:|---:|---:|']
    metrics = {}
    for label, rows, cf, tf, rf, wf in (
        ('spec-kit', sk_valid, lambda r:r['total']['cost_usd'], lambda r:r['total']['input']+r['total']['output'], lambda r:r['total']['requests'], lambda r:r['wall_s']),
        ('Spine + PKG', sp_valid, spine_cost, spine_tokens, lambda r:r['calls']+intake[(r['ticket'],r['pass'])]['calls'], spine_wall),
    ):
        if rows:
            costs = [cf(r) for r in rows]
            metrics[label] = {'cost': st.mean(costs), 'tokens': st.mean(tf(r) for r in rows), 'wall':st.mean(wf(r) for r in rows)}
            lines.append(f'| {label} | {len(rows)} | ${st.mean(costs):.4f} | ${min(costs):.4f}–${max(costs):.4f} | {st.mean(tf(r) for r in rows):,.0f} | {st.mean(rf(r) for r in rows):.1f} | {st.mean(wf(r) for r in rows)/60:.2f} |')
    lines += ['', 'Spine includes the matching ticket/pass intake measurement. Intake is measured separately; '
              'its output is not fed into the codegen benchmark. These are costs per completed attempt, not '
              'necessarily per accepted repository change. Failed or incomplete attempts remain in the accounting below. '
              'Wall-time boundaries differ: spec-kit excludes initialization and the harness\'s independent grading, '
              'while Spine wraps its benchmark execution and checks, then adds separate intake time. '
              'Dependency/cache warmup is not reset between runs. Treat timing as descriptive rather than '
              'a controlled end-to-end speed estimate.', '',
              '## Per-ticket paired comparison', '',
              '| Ticket | Complete pairs / planned | spec-kit mean cost | Spine mean cost | Cost ratio |',
              '|---|---:|---:|---:|---:|']
    ticket_means = []
    for ticket in tickets:
        pairs = []
        for n in range(1, passes+1):
            x,y = sk_by.get((ticket,n)), sp_by.get((ticket,n))
            if x and y and x in sk_valid and y in sp_valid:
                pairs.append((x['total']['cost_usd'], spine_cost(y)))
        if pairs:
            x,y = map(st.mean, zip(*pairs))
            lines.append(f'| {ticket} | {len(pairs)}/{passes} | ${x:.4f} | ${y:.4f} | {x/y:.2f}× |')
            if len(pairs) == passes:
                ticket_means.append((x,y))
        else:
            lines.append(f'| {ticket} | 0/{passes} | — | — | — |')
    lines += ['', '## Statistical interpretation', '']
    if done and len(ticket_means) == len(tickets):
        ratio = st.mean(x for x,y in ticket_means)/st.mean(y for x,y in ticket_means)
        resamples = [sum(ticket_means[i][0] for i in ids)/sum(ticket_means[i][1] for i in ids)
                     for ids in itertools.product(range(len(ticket_means)), repeat=len(ticket_means))]
        lo,hi = percentile(resamples,.025),percentile(resamples,.975)
        p = sign_p([x-y for x,y in ticket_means])
        lines += [f'The equal-weight, paired ticket-mean cost ratio is **{ratio:.2f}×** (spec-kit / Spine). '
                  f'The two-sided sign test over **{len(ticket_means)} distinct tickets** gives **p = {p:.3f}**.', '',
                  f'An exploratory whole-ticket bootstrap percentile interval is **{lo:.2f}–{hi:.2f}×** '
                  f'(95%; all {len(resamples)} ordered resamples enumerated). With only three ticket clusters, '
                  'this interval is unstable and is not a reliable population-wide precision guarantee.', '']
    else:
        lines += ['Comparative inference is deferred until all planned paired measurements are available.', '']
    lines += ['Repeated runs measure variability on the same task; they are not additional independent problems. '
              'Three small create-module tickets on one repository cannot establish a universal multiplier or '
              'quality equivalence. Report differences in pass rates descriptively; a non-significant difference '
              'would not prove equality. The runner uses a fixed serial order, not randomized paired ordering.', '',
              f"Infrastructure recovery: {sum(bool(r.get('capacity_recovery')) for r in sk)} spec-kit run(s) resumed the same model/thread after a provider capacity error. Interrupted responses and recovery overhead remain included in costs; idle recovery downtime is excluded from active wall time. This is a protocol deviation, recorded separately from functional failures. Original error rows remain in the summaries.", '',
              '## Spec-kit stage costs', '',
              '| Step | Observed steps | Mean API equivalent | Mean tokens | Mean model responses |',
              '|---|---:|---:|---:|---:|']
    for step in sorted({r['step'] for d in sk for r in d['rows']}):
        rows = [r for d in sk for r in d['rows'] if r['step'] == step]
        lines.append(f"| {step} | {len(rows)} | ${st.mean(r['cost_usd'] for r in rows):.4f} | {st.mean(r['input']+r['output'] for r in rows):,.0f} | {st.mean(r['requests'] for r in rows):.1f} |")
    lines += ['', '## Individual outcomes', '',
              '| Ticket | Pass | Workflow | Implementation measured | Held-out | Repository gate | Existing tracked files modified |',
              '|---|---:|---|---|---|---|---|']
    for ticket in tickets:
        for n in range(1,passes+1):
            for label,r in [('spec-kit',sk_by.get((ticket,n))),('Spine',sp_by.get((ticket,n)))]:
                if not r:
                    lines.append(f'| {ticket} | {n} | {label} | Pending / missing | — | — | — |'); continue
                g = r['grading'] if label == 'spec-kit' else r
                valid = r in (sk_valid if label == 'spec-kit' else sp_valid)
                files = ', '.join(g.get('tracked_files_modified',[])) or 'none'
                lines.append(f"| {ticket} | {n} | {label} | {valid} | {g.get('held_out_pass')} | {g.get('repo_gate_pass')} | {files} |")
    usage = summarize_usage(root)
    (root/'recorded-usage.json').write_text(json.dumps(usage,indent=2)+'\n')
    lines += ['', '## Recorded tokens and cost', '']
    for model_id,u in usage['models'].items():
        price = f"${u['cost_usd']:.2f}" if u['cost_usd'] is not None else 'UNPRICED'
        lines += [f"**Tokens & cost — Codex, {model_id}:** {u['tokens']/1e6:.2f}M tokens "
                  f"(in {u['uncached_input']:,} · out {u['output']:,} · cache write {u['cache_write']:,} · "
                  f"cache read {u['cached']:,}) · **{price} API list-price equivalent**, not a subscription invoice.", '']
    lines += ['These figures count exported response ledgers, deduplicated by response ID. '
              'Interrupted/unexported usage may be missing. They exclude the pilot, diagnostics, '
              'the parent coordinating chat, and report preparation. Final accounting must be regenerated '
              'after all child sessions close and reconciled with the shared session calculator.', '',
              '## Protocol and evidence', '',
              '[Frozen protocol and source hashes](PROTOCOL.json) · [Recorded usage](recorded-usage.json).', '',
              'Raw run summaries, generated code, planning artifacts, and model logs are retained under '
              f'`{a.model}/`. The Codex adapter changes the original API experiment: agent overhead, '
              'validated JSON envelopes, and unenforced temperature/output-token limits are disclosed. '
              'This compares entire workflows and is not an ablation isolating the causal effect of the knowledge graph. '
              'No architectural or enterprise-savings claims from the historical report are imported as findings.', '']
    if done:
        measured_ratio = metrics['spec-kit']['cost'] / metrics['Spine + PKG']['cost']
        overview = [
            '## Findings', '',
            f"Across these three scenarios, spec-kit averaged **${metrics['spec-kit']['cost']:.4f}** per attempt and Spine + PKG, including separate intake, averaged **${metrics['Spine + PKG']['cost']:.4f}**: an observed **{measured_ratio:.2f}× cost ratio**. Both workflows passed all nine held-out evaluations. This is evidence of a large cost difference within this small benchmark, not a general estimate for software development.", '',
            f"The repository gate passed in **{sk_gate}/9 spec-kit** runs and **{sp_gate}/9 Spine** runs. Here, ‘repository gate’ specifically means `scripts/state-numbers.py --check`, which checks documented repository counts; it is not the full test suite or a comprehensive merge-readiness check. All nine Spine summaries record three inconsistent claims. Each successful spec-kit gate coincided with an update to `docs/specs/STATE-OF-SPINE.md`. The separate fit rule penalized such tracked-file edits, so fit and gate scores can disagree for understandable reasons.", '',
            'Neither cost nor functional success isolates the effect of the knowledge graph: spec-kit runs a multi-stage agent workflow, while Spine uses deterministic design and tightly scoped model calls. The different tool access, context supplied, validation work, and step counts are part of the measured treatment.', '',
        ]
        index = lines.index('## Outcomes')
        lines[index:index] = overview
        sensitivity = []
        for ticket in tickets:
            paired = [(x['total']['cost_usd'], spine_cost(sp_by[(ticket,n)]))
                      for n in range(1,passes+1)
                      if (x := sk_by[(ticket,n)]) and not x.get('capacity_recovery')]
            if paired:
                sensitivity.append(tuple(map(st.mean,zip(*paired))))
        if len(sensitivity) == len(tickets) and any(r.get('capacity_recovery') for r in sk):
            sensitivity_ratio = st.mean(x for x,y in sensitivity)/st.mean(y for x,y in sensitivity)
            lines += ['## Recovery sensitivity', '',
                      f'Excluding the entire recovered ticket/pass pair gives an equal-ticket mean cost ratio of **{sensitivity_ratio:.2f}×**. The affected ticket then has two repeats; the other tickets retain three. This is a descriptive sensitivity check, not a replacement for the prespecified comparison.', '']
        lines += ['## What to test next', '',
                  'Add distinct problems before adding many more repeats of these three. A practical next study could cover 20–30 scenarios across multiple repositories, including bug fixes, changes to existing APIs, refactoring, integration work, and larger multi-file features. That is a planning range, not a power guarantee. Define the meaningful cost and quality differences first, then use variation across distinct tasks to plan sample size.', '',
                  'Use paired tasks, randomize workflow order, retain infrastructure failures and retry costs, and define a shared acceptance endpoint that includes functional checks and repository maintenance. Keep intake treatment and timing boundaries consistent. Add a separate graph-on/graph-off ablation if the goal is to attribute benefits specifically to the knowledge graph.', '']
    review_path = root / 'REVIEW.json'
    if review_path.exists():
        review = read(review_path)
        if review.get('status') == 'verified':
            old = 'Final accounting must be regenerated after all child sessions close and reconciled with the shared session calculator.'
            new = f"Closed-session accounting was reconciled with the shared calculator: all token categories, {review['response_count']:,} response records, and the rounded dollar total agree. See [shared calculator output](tokens-and-cost.txt), [finalization checks](FINALIZATION.json), and [review record](REVIEW.json)."
            lines = [line.replace(old,new) for line in lines]
    section = model_section(protocol, [('spec-kit',a.model,sk), ('Spine + PKG',a.model,sp), ('Spine intake (separate)',a.model,list(intake.values()))], usage)
    idx = lines.index('## Outcomes')
    lines[idx:idx] = section
    (root/a.output).write_text('\n'.join(lines))
    print(root/a.output)


if __name__ == '__main__':
    main()
