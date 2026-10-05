#!/usr/bin/env python3
"""Portable, paired-by-scenario summary for any catalog size; no model calls."""
import argparse
import json
import math
import statistics as st
from pathlib import Path

from model_report import model_section
from report_usage import summarize_usage


def completed(d):
    good={r['step'] for r in d.get('rows',[]) if not r.get('exit') and not r.get('error') and not r.get('is_error')}
    return bool(d.get('reached_code')) and not d.get('paused_for_checklist') and not d.get('stopped_at_job_cap_before') and all(
        not (r.get('exit') or r.get('error') or r.get('is_error')) or d.get('recovered_steps',{}).get(r['step']) in good for r in d.get('rows',[]))


def sign_p(differences):
    signs=[d>0 for d in differences if d!=0]
    if not signs:return 1.0
    n=len(signs);k=min(sum(signs),n-sum(signs))
    return min(1.,2*sum(math.comb(n,j) for j in range(k+1))/2**n)


def read_rows(paths):
    return [json.loads(p.read_text()) for p in sorted(paths)]


def indexed(rows, expected):
    result={}
    for d in rows:
        key=(d['ticket'],d['pass'])
        if key in result or key not in expected:raise ValueError(f'Duplicate or unexpected measurement: {key}')
        result[key]=d
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',required=True,type=Path)
    a=ap.parse_args();root=a.results.resolve()
    exp=json.loads((root/'EXPERIMENT.json').read_text())
    if exp.get('evaluation_mode')=='tokens-only':
        from report_project import report
        report(root)
        return
    expected={(t,n) for t in exp['tickets'] for n in range(1,exp['passes']+1)}
    lines=['# Scenario comparison results','','Costs are API list-price equivalents, not subscription invoices. Intake is measured separately and added to the matching ticket/pass; its output is not fed into codegen.','',
           f"Planned: {len(exp['tickets'])} distinct scenarios × {exp['passes']} repeats × {len(exp['arms'])} workflows per model. Fixed execution order; one target repository.", '']
    usage=summarize_usage(root)
    inventory=[]
    for model in exp['models']:
        if 'speckit' in exp['arms']:
            inventory.append(('spec-kit',model,read_rows((root/model).glob('speckit/*/summary.json'))))
        if 'spine' in exp['arms']:
            inventory.append(('Spine + PKG',model,read_rows((root/model).glob('spine/pass*/*/summary.json'))))
            inventory.append(('Spine intake (separate)',model,[d for rows in read_rows((root/model).glob('intake/pass*.json')) for d in rows]))
    lines += model_section(exp,inventory,usage)
    for model in exp['models']:
        sk=indexed(read_rows((root/model).glob('speckit/*/summary.json')),expected)
        sp=indexed(read_rows((root/model).glob('spine/pass*/*/summary.json')),expected)
        it=indexed([d for rows in read_rows((root/model).glob('intake/pass*.json')) for d in rows],expected)
        for d in [*sk.values(),*sp.values(),*it.values()]:
            if d.get('scenario_fingerprint') != exp['scenario_fingerprint']:
                raise ValueError('Measurement scenario fingerprint differs from EXPERIMENT.json')
        valid_sk={k:d for k,d in sk.items() if completed(d)}
        valid_sp={k:d for k,d in sp.items() if not d.get('aborted') and d.get('usage_complete',True) and k in it}
        cost_sp=lambda k:sp[k]['cost_usd']+it[k]['cost_usd']
        lines += [f'## {model}','','| Workflow | Completed / planned | Held-out passes | State-count gate passes | Mean cost / completed attempt |','|---|---:|---:|---:|---:|']
        for label,rows,gf,cf in [('spec-kit',valid_sk,lambda d:d['grading'],lambda k:sk[k]['total']['cost_usd']),('Spine + PKG',valid_sp,lambda d:d,cost_sp)]:
            if ('speckit' if label=='spec-kit' else 'spine') not in exp['arms']:continue
            n=len(rows);mean=f'${st.mean(cf(k) for k in rows):.4f}' if n else '—'
            lines += [f"| {label} | {n}/{len(expected)} | {sum(bool(gf(d).get('held_out_pass')) for d in rows.values())}/{n} | {sum(bool(gf(d).get('repo_gate_pass')) for d in rows.values())}/{n} | {mean} |"]
        lines += ['','Missing/incomplete runs are not counted as completed measurements. The state-count gate is not the full test suite or a merge-readiness guarantee. Mean costs are not cost per accepted change.','',
                  '| Scenario | Kind | Complete paired repeats | spec-kit mean | Spine mean | Ratio |','|---|---|---:|---:|---:|---:|']
        means=[]
        for ticket in exp['tickets']:
            keys=[(ticket,n) for n in range(1,exp['passes']+1) if (ticket,n) in valid_sk and (ticket,n) in valid_sp]
            kind=next(d['kind'] for d in exp['scenarios'] if d['key']==ticket)
            if keys:
                x=st.mean(sk[k]['total']['cost_usd'] for k in keys);y=st.mean(cost_sp(k) for k in keys)
                ratio=f'{x/y:.2f}×' if y else 'undefined (zero cost)'
                lines += [f'| {ticket} | {kind} | {len(keys)}/{exp["passes"]} | ${x:.4f} | ${y:.4f} | {ratio} |']
                if len(keys)==exp['passes']:means.append((x,y))
            else:lines += [f'| {ticket} | {kind} | 0/{exp["passes"]} | — | — | — |']
        if len(means)==len(exp['tickets']):
            y=st.mean(y for x,y in means)
            ratio=f'{st.mean(x for x,y in means)/y:.2f}×' if y else 'undefined'
            lines += ['',f'Equal-weight scenario-mean cost ratio: **{ratio}**. Two-sided sign test across **{len(means)} distinct scenarios**: **p = {sign_p([x-y for x,y in means]):.6g}**.']
        else:lines += ['','Inference deferred until all planned paired repeats are complete.']
        lines += ['','Repeated runs are not independent problems. The sign test concerns the direction of scenario-level differences, ignores magnitude, and assumes independent scenario signs. Shared repository/task effects limit generalization. No quality-equivalence claim follows from tied outcomes.','']
    (root/'recorded-usage.json').write_text(json.dumps(usage,indent=2)+'\n')
    lines += ['## Exported model usage','']
    for model,u in usage['models'].items():
        dollars=f"${u['cost_usd']:.2f}" if u['cost_usd'] is not None else 'UNPRICED'
        lines += [f"Codex {model}: {u['tokens']:,} tokens (uncached input {u['uncached_input']:,}; cached input {u['cached']:,}; cache write {u['cache_write']:,}; output {u['output']:,}), {dollars} API equivalent.",'']
    lines += ['Exported usage includes recorded failed attempts; unexported interrupted usage can be missing. No ledger means unknown usage, not zero. Retain failure markers and audit transcripts before claiming complete accounting. Wall-time comparisons require aligned boundaries.','']
    (root/'summary.md').write_text('\n'.join(lines))
    print(root/'summary.md')


if __name__=='__main__':main()
