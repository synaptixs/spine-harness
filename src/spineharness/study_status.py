"""Compact read-only status for a running study, without printing prompts or credentials."""
import json
from datetime import UTC, datetime
from pathlib import Path

root = Path('results/study-20260929')
logs = sorted((root/'gpt-6-sol/logs').glob('*.log'), key=lambda p:p.stat().st_mtime)
summaries = list((root/'gpt-6-sol').glob('speckit/*/summary.json')) + list((root/'gpt-6-sol').glob('spine/pass*/*/summary.json'))
out = {'utc': datetime.now(UTC).isoformat(), 'saved_ticket_arm_summaries':len(summaries)}
if logs:
    f=logs[-1]
    out['latest_log']=f.name
    lines=f.read_text(errors='replace').splitlines()
    out['latest_lines']=[s[:600] for s in lines if s.startswith(('[new-', '[spine ', '{', 'Traceback', 'RuntimeError'))][-1:]
for name in ['JOB_FAILED','QUOTA_STOP']:
    if (root/name).exists():
        out[name]=(root/name).read_text()[:500]
print(json.dumps(out,indent=2))
