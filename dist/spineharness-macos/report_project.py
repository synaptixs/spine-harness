#!/usr/bin/env python3
"""Evidence report for Jira token-only runs, including complete proposed patches."""
import argparse
import json
from pathlib import Path
from report_usage import summarize_usage
from model_report import model_section


def report(root):
    root=Path(root).resolve();exp=json.loads((root/'EXPERIMENT.json').read_text())
    if exp.get('evaluation_mode')!='tokens-only':raise ValueError('This report requires a token-only project experiment')
    usage=summarize_usage(root);inventory=[];sections=[]
    expected={(t,n) for t in exp['tickets'] for n in range(1,exp['passes']+1)}
    from report_results import indexed, read_rows
    from project_adapter import source_fingerprint
    for model in exp['models']:
        for label,arm,pattern in [('spec-kit','speckit','speckit/*/summary.json'),('Spine + PKG','spine','spine/pass*/*/summary.json')]:
            if arm not in exp['arms']:continue
            files=sorted((root/model).glob(pattern));rows=read_rows(files);indexed(rows,expected)
            if any(r.get('scenario_fingerprint')!=exp['scenario_fingerprint'] for r in rows):raise ValueError('Mixed scenario fingerprints')
            inventory.append((label,model,rows))
            for path,row in zip(files,rows):
                total=row.get('total',{})
                tokens=total.get('tokens')
                if tokens is None and 'prompt_tokens' in row and 'completion_tokens' in row:
                    tokens=row['prompt_tokens']+row['completion_tokens']
                token_text=f'{tokens:,}' if tokens is not None else 'unknown'
                cost=total.get('cost_usd',row.get('cost_usd'))
                status='infrastructure abort' if row.get('aborted') else 'checklist paused' if row.get('paused_for_checklist') else 'budget stopped' if row.get('stopped_at_job_cap_before') else 'saved attempt; inspect checks'
                sections += [f'## {row["ticket"]} — {label}, {model}, pass {row["pass"]}', '',
                    f'Status: **{status}**. Independent correctness: **unverified**.',
                    f'Recorded attempt tokens: **{token_text}**. API list-price equivalent: **{cost if cost is not None else "unknown"} USD**.', '',
                    'Project checks:', '```json',json.dumps(row.get('project_checks',[]),indent=2),'```','']
                changes=path.parent/'CHANGES.md'
                if changes.exists():sections += [changes.read_text(),'']
                else:sections += ['No proposed-change artifact was captured; this is not evidence of a completed implementation.','']
            summarized={p.parent for p in files}
            evidence_pattern='speckit/*/CHANGES.md' if arm=='speckit' else 'spine/pass*/*/CHANGES.md'
            for evidence in sorted((root/model).glob(evidence_pattern)):
                if evidence.parent not in summarized:
                    sections += [f'## Incomplete {label} attempt: {evidence.parent.name}', '', 'No summary exists; exported usage may be partial.', '', evidence.read_text(), '']
            missing=expected-{(r['ticket'],r['pass']) for r in rows}
            if missing:sections += [f'**Missing {label} summaries for {model}:** '+', '.join(f'{t}/pass{n}' for t,n in sorted(missing)),'']
    lines=['# Jira benchmark — proposed changes and token usage','',
           'No changes are applied to the original repository or Jira by this reporting command. Proposed patches are evidence from disposable copies. '
           'Token consumption is not a correctness or quality score. Costs are API list-price equivalents, not subscription charges.','',
           f'Repository: {exp["project"]["repository_url"]}',f'Baseline: `{exp["project"]["baseline_commit"]}`','',
           'Shared Jira normalization is deterministic and uses zero model tokens. Its frozen output feeds both workflows; '
           'no unused separate Spine intake charge is added in this mode.','']
    prep=root/'PREPARATION.json'
    if prep.exists():
        before=json.loads(prep.read_text())['source_before']
        try:unchanged=source_fingerprint(exp['project']['source_repo'])==before
        except Exception:unchanged='unavailable'
        lines += [f'Original repository matches preparation fingerprint: **{unchanged}**. External/user changes can also affect this comparison.','']
    lines+=model_section(exp,inventory,usage)
    lines+=['## Reconciled exported responses','','```json',json.dumps(usage,indent=2),'```','',
            'This ledger includes exported failure/retry responses. Missing exports mean unknown consumption. '
            'Jira write prevention is enforced by the importer call policy; this report is not a Jira server audit.','']+sections
    (root/'recorded-usage.json').write_text(json.dumps(usage,indent=2)+'\n')
    (root/'RESULTS.md').write_text('\n'.join(lines));print(root/'RESULTS.md')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--results',required=True,type=Path)
    report(p.parse_args().results)
