#!/usr/bin/env python3
"""Portable, closed-run reports, usage reconciliation, checksums and evidence archives."""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone

from codex_usage import PRICES, PRICE_BASIS, cost, total

PATTERNS = ('*/speckit/*/session-rollout-*.jsonl', '*/spine/pass*/codex-calls/*/rollout-*.jsonl')
BLOCKED_NAMES = {'auth.json', 'mcp.json', '.mcp.json', 'config.toml', '.env', 'benchmark.env'}
SECRET = re.compile(rb'\bsk-[A-Za-z0-9_-]{20,}|\b(?:ghp|gho|github_pat)_[A-Za-z0-9_]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"(?:access_token|refresh_token|id_token)"\s*:\s*"[^"\s]{16,}"')

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')

def read_ledgers(root):
    records, origins = {}, {}
    for path in sorted({p for pattern in PATTERNS for p in root.glob(pattern)}):
        model = None
        for line in path.read_text().splitlines():
            try: row = json.loads(line)
            except ValueError: continue
            p = row.get('payload', {})
            if row.get('type') == 'turn_context': model = p.get('model')
            if row.get('type') != 'token_usage_record': continue
            rid = p.get('response_id')
            if not rid or not model: raise ValueError(f'Unattributed usage record in {path}')
            item = {'response_id': rid, 'model': model, 'usage': p['usage']}
            if rid in records and records[rid] != item: raise ValueError('Conflicting response ledger')
            records[rid] = item
            origins.setdefault(rid, set()).add(str(path.relative_to(root)))
    # Portable exports retain token records without full model conversation history.
    saved = root / 'response-ledger.json'
    if not records and saved.exists():
        portable = json.loads(saved.read_text())
        for item in portable['responses']:
            rid = item['response_id']
            if rid in records and records[rid] != item: raise ValueError('Conflicting portable ledger')
            records[rid] = item
        origins = {k: set(v) for k, v in portable.get('origins', {}).items()}
    return records, {k: sorted(v) for k, v in origins.items()}

def usage_total(records):
    result = {}
    for model in sorted({r['model'] for r in records.values()}):
        u = total({rid: r['usage'] for rid, r in records.items() if r['model'] == model})
        result[model] = {**u, 'tokens': u['input'] + u['output'],
                         'uncached_input': u['input'] - u['cached'] - u['cache_write'],
                         'api_list_price_equivalent_usd': cost(model, u) if model in PRICES else None}
    return result

def unknown_calls(root):
    result = []
    for request in root.glob('*/spine/pass*/codex-calls/*/request.json'):
        p = request.parent / 'usage.json'
        if not p.exists() or not json.loads(p.read_text()).get('usage_complete', False):
            result.append(str(request.parent.relative_to(root)))
    for p in root.glob('*/speckit/*/INCOMPLETE.txt'):
        result.append(str(p.parent.relative_to(root)))
    # An abrupt stop may leave a request without an incomplete marker.
    for p in root.glob('*/speckit/*'):
        if p.is_dir() and not (p / 'summary.json').exists():
            result.append(str(p.relative_to(root)))
    saved = root / 'response-ledger.json'
    if saved.exists(): result.extend(json.loads(saved.read_text()).get('unknown_calls', []))
    return sorted(set(result))

def collect_rows(root, exp, records, origins):
    rows = []
    for model in exp.get('models', []):
        for arm, pattern in [('speckit', 'speckit/*/summary.json'), ('spine', 'spine/pass*/*/summary.json')]:
            if arm not in exp.get('arms', []): continue
            seen = set()
            for p in sorted((root / model).glob(pattern)):
                s = json.loads(p.read_text()); key = (s['ticket'], s['pass'])
                if key in seen: raise ValueError('Duplicate issue/pass summary')
                seen.add(key)
                if s.get('scenario_fingerprint') != exp.get('scenario_fingerprint'):
                    raise ValueError('Summary/catalog fingerprint mismatch')
                prefix = str(p.parent.relative_to(root)) + '/'
                if arm == 'spine':
                    # Spine per-ticket summaries own response IDs only when a pass has one ticket.
                    # Multi-ticket pass totals remain in overall USAGE.json; do not invent attribution.
                    prefix = str(p.parent.parent.relative_to(root)) + '/codex-calls/' if len(exp['tickets']) == 1 else None
                ids = {rid: records[rid] for rid, files in origins.items() if prefix and any(f.startswith(prefix) for f in files)}
                u = usage_total(ids).get(model)
                reported = s.get('total', {})
                tokens = reported.get('tokens', s.get('prompt_tokens', 0) + s.get('completion_tokens', 0))
                uncertain = s.get('usage_complete') is False or s.get('aborted')
                status = ('infrastructure abort' if s.get('aborted') else 'checklist paused' if s.get('paused_for_checklist') else
                          'budget stopped' if s.get('stopped_at_job_cap_before') else 'completed workflow')
                rows.append({'ticket': key[0], 'pass': key[1], 'arm': arm, 'model': model, 'status': status,
                    'known_tokens': u['tokens'] if u else tokens if tokens else None,
                    'usage_complete': not uncertain and status == 'completed workflow' and bool(records) and
                                      bool(u or (arm == 'spine' and s.get('usage_complete') and tokens)),
                    'token_basis': 'deduplicated exported responses' if u else 'saved per-ticket summary; overall ledger reconciled separately',
                    'api_list_price_equivalent_usd': u['api_list_price_equivalent_usd'] if u else reported.get('cost_usd', s.get('cost_usd')) if not uncertain else None,
                    'own_tests_pass': s.get('tests_pass', s.get('grading', {}).get('own_tests_pass')),
                    'project_checks_pass': bool(s.get('project_checks')) and all(c.get('exit') == 0 for c in s.get('project_checks', [])),
                    'summary': str(p.relative_to(root)), 'wall_s': s.get('wall_s'),
                    'proposed_changes': str((p.parent / 'changes.patch').relative_to(root)) if (p.parent / 'changes.patch').exists() else None,
                    'acceptance': 'not evaluated'})
            for ticket in exp.get('tickets', []):
                for n in range(1, exp.get('passes', 1) + 1):
                    if (ticket, n) not in seen:
                        rows.append({'ticket': ticket, 'pass': n, 'arm': arm, 'model': model, 'status': 'missing/incomplete',
                                     'known_tokens': None, 'api_list_price_equivalent_usd': None, 'usage_complete': False,
                                     'own_tests_pass': None, 'project_checks_pass': None, 'acceptance': 'not evaluated'})
    return rows

def run_acceptance(root, rows):
    from project_adapter import sandboxed_command, clean_test_env
    config = root / 'ACCEPTANCE_TESTS.json'
    suites = json.loads(config.read_text()) if config.exists() else {}
    project = json.loads((root / 'PROJECT.json').read_text())
    outcomes = []
    for row in rows:
        tests = suites.get(row['ticket'], [])
        if not tests or row['status'] != 'completed workflow': continue
        s = json.loads((root / row['summary']).read_text())
        repo = s.get('worktree')
        if not repo and row['arm'] == 'spine':
            log = root / row['model'] / 'logs' / f'spine-p{row["pass"]}.log'
            for line in log.read_text().splitlines() if log.exists() else []:
                if line.startswith(f'=== {row["ticket"]} ') and ' → ' in line: repo = line.split(' → ', 1)[1]
        tag = f'{row["model"]}-{row["arm"]}-{row["ticket"]}-p{row["pass"]}'
        out = root / 'acceptance-results' / tag; out.mkdir(parents=True, exist_ok=True)
        if (out / 'result.json').exists():
            outcomes.append(json.loads((out / 'result.json').read_text())); continue
        result = {'tag': tag, 'ticket': row['ticket'], 'pass': row['pass'], 'arm': row['arm'], 'model': row['model'],
                  'repo': repo, 'feedback_supplied_to_model': False, 'scope': 'Frozen selected acceptance checks; not full ticket certification'}
        if not repo or not Path(repo).exists():
            result.update(exit=None, error='Disposable repository unavailable; no audit was run')
        else:
            paths = []
            for item in tests:
                p = root / item['path']
                if hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']: raise ValueError('Frozen acceptance test changed')
                paths.append(str(p))
            argv, temp = sandboxed_command([project['python'], '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                '--import-mode=importlib', *paths, '--junitxml=' + str(Path(repo) / '.benchmark-tmp/acceptance.xml')], repo)
            env = clean_test_env(repo, project['source_paths']); env['TMPDIR'] = str(temp)
            try:
                p = subprocess.run(argv, cwd=repo, env=env, capture_output=True, text=True, timeout=300)
                result.update(exit=p.returncode)
                (out / 'checks.log').write_text(p.stdout + p.stderr)
                xml = Path(repo) / '.benchmark-tmp/acceptance.xml'
                if xml.exists(): shutil.copy2(xml, out / 'checks.xml')
            except subprocess.TimeoutExpired:
                result.update(exit=None, error='Acceptance test timeout at 300 seconds')
        dump(out / 'result.json', result); outcomes.append(result)
    return outcomes

def archive_evidence(root, out):
    """Copy results only, never the workspace, login, .env, MCP config or symlink targets."""
    archive = out / 'results-and-artifacts.zip'
    files = []
    for p in root.rglob('*'):
        if not p.is_file() or p.is_symlink() or p.is_relative_to(out): continue
        rel = p.relative_to(root)
        if any(x.startswith('.') or x in ('__pycache__', '.venv', 'accounting-ledger') for x in rel.parts): continue
        if p.name in BLOCKED_NAMES or p.name.startswith('.env') or p.suffix in ('.zip', '.pyc', '.env'): continue
        # Full conversations remain local. Portable response ledger retains every recorded usage item.
        if p.suffix == '.jsonl' or p.name in ('request.json', 'stderr.txt'): continue
        if p.suffix not in ('.json', '.md', '.html', '.csv', '.patch', '.log', '.txt', '.xml', '.py', '.lock', ''): continue
        data = p.read_bytes()
        if SECRET.search(data): raise ValueError(f'Possible credential in {rel}; inspect locally before packaging')
        files.append((p, rel))
    for p in out.iterdir():
        if p.is_file() and p.name not in ('results-and-artifacts.zip', 'results-and-artifacts.zip.sha256', 'MANIFEST.json'):
            if SECRET.search(p.read_bytes()): raise ValueError('Possible credential in generated report: ' + p.name)
            files.append((p, Path('deliverables') / p.name))
    hashes = {str(rel): hashlib.sha256(p.read_bytes()).hexdigest() for p, rel in files}
    dump(out / 'MANIFEST.json', {'sha256': hashes, 'raw_model_sessions_included': False,
         'scope': 'Saved reports, logs, generated artifacts, proposed patches and response-only token ledger. Credentials and full conversations excluded.'})
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for p, rel in sorted(files, key=lambda v: str(v[1])): z.write(p, str(Path(root.name) / rel))
        z.write(out / 'MANIFEST.json', str(Path(root.name) / 'deliverables/MANIFEST.json'))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('ZIP integrity failure')
    (out / 'results-and-artifacts.zip.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n')
    return archive

def finalize(root, run_audits=False):
    root = Path(root).resolve()
    if (root / 'RUNNING.json').exists() or not (root / 'FINISHED').exists():
        raise ValueError('Refusing accounting while the run is active or not explicitly closed')
    exp_path = root / 'EXPERIMENT.json'
    if exp_path.exists(): exp = json.loads(exp_path.read_text())
    else:
        c = json.loads((root / 'RUN_CONFIG.json').read_text())
        exp = {'models': [c['model']], 'arms': ['speckit', 'spine'], 'tickets': c['issues'], 'passes': c['passes']}
    records, origins = read_ledgers(root)
    rows = collect_rows(root, exp, records, origins)
    unknown = unknown_calls(root)
    audits = run_acceptance(root, rows) if run_audits else [json.loads(p.read_text()) for p in root.glob('acceptance-results/*/result.json')]
    for row in rows:
        for a in audits:
            if all(row[k] == a[k] for k in ('model', 'arm', 'ticket', 'pass')):
                row['acceptance'] = 'selected checks passed' if a.get('exit') == 0 else 'selected checks failed' if a.get('exit') is not None else 'unavailable'
    usage = {'price_basis': PRICE_BASIS, 'models': usage_total(records), 'unknown_calls': unknown,
             'complete': bool(records) and not unknown and all(r['usage_complete'] for r in rows),
             'missing_records_are_zero': False, 'supervision_excluded': True}
    dump(root / 'response-ledger.json', {'responses': list(records.values()), 'origins': origins, 'unknown_calls': unknown})
    out = root / 'deliverables'; out.mkdir(exist_ok=True)
    dump(out / 'USAGE.json', usage); dump(out / 'RESULTS.json', {'runs': rows, 'audits': audits})
    fieldnames = ['ticket', 'pass', 'arm', 'model', 'status', 'known_tokens', 'api_list_price_equivalent_usd', 'usage_complete', 'own_tests_pass', 'project_checks_pass', 'acceptance']
    with (out / 'RESULTS.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore'); writer.writeheader(); writer.writerows(rows)
    lines = ['# Jira benchmark final report', '', f'Generated: {datetime.now(timezone.utc).isoformat()}', '',
        '**Scope:** matched frozen Jira issues and baseline, spec-kit versus Spine + PKG through the Codex subscription adapter.',
        'Workflow completion, generated tests, project regression checks and selected acceptance checks are separate outcomes. Full ticket correctness remains unverified.', '',
        '| Issue | Pass | Workflow | Status | Recorded tokens | API-equivalent USD | Own tests | Project checks | Acceptance |',
        '|---|---:|---|---|---:|---:|---|---|---|']
    for r in rows:
        token = str(r['known_tokens']) if r['known_tokens'] is not None else 'unknown'
        if not r['usage_complete']: token += ' (incomplete)'
        price = 'unknown' if r['api_list_price_equivalent_usd'] is None else f"${r['api_list_price_equivalent_usd']:.6f}"
        if not r['usage_complete'] and price != 'unknown': price += ' (known subtotal)'
        lines.append(f'| {r["ticket"]} | {r["pass"]} | {r["arm"]} | {r["status"]} | {token} | {price} | {r["own_tests_pass"]} | {r["project_checks_pass"]} | {r["acceptance"]} |')
    lines += ['', '## Token usage and cost', '', 'Costs below are **API list-price equivalents, not subscription charges**. Rates are the packaged snapshot in codex_usage.py. Cached input is included in input; reasoning is included in output. Supervisor work is excluded.', '']
    for model, u in usage['models'].items():
        dollars = 'unpriced' if u['api_list_price_equivalent_usd'] is None else f'${u["api_list_price_equivalent_usd"]:.6f}'
        lines += [f'- Codex / {model}: {u["tokens"]:,} recorded tokens (uncached input {u["uncached_input"]:,}; cache read {u["cached"]:,}; cache write {u["cache_write"]:,}; output {u["output"]:,}) · {dollars} API list-price equivalent.']
    if not usage['models']: lines += ['No response usage was exported. Consumption is **unknown**, not zero.']
    if not usage['complete']: lines += ['', '**Incomplete accounting:** missing/failed attempts or response records prevent a complete total. Recorded figures are known subtotals; never substitute zero for unknown consumption.']
    lines += ['', '## Evidence and interpretation', '',
        '- [Machine-readable results](RESULTS.json), [CSV](RESULTS.csv), [usage](USAGE.json), and [artifact inventory](ARTIFACTS.md).',
        '- Frozen issue snapshots, planning files, generated code artifacts, check output and patches are preserved in the evidence archive.',
        '- Full local model session logs stay in the run directory; the portable archive contains a deduplicated response-only usage ledger.',
        '- Missing acceptance tests mean correctness was not independently evaluated. Passing generated tests alone is not a completion guarantee.',
        '- One issue is not evidence of statistical significance. Repeated passes on the same issue are not independent problems.',
        '- Changes after audit feedback must be separately measured and labeled post-audit continuation. Preserve the original result and account for both.',
        '- Failed runs remain visible. No automatic full retry is performed; choose fresh run paths after diagnosing a failure.',
        '- Both workflows start from the same committed baseline. Prerequisites must be prepared equally; they are not inherited from another workflow.',
        '- Fixed serial order, cache state and different timing boundaries prevent a controlled speed comparison.', '']
    verification = root / 'SOURCE_VERIFICATION.json'
    if verification.exists():
        state = json.loads(verification.read_text()).get('unchanged')
        lines += ['Source checkout fingerprint after execution: ' + ('unchanged' if state is True else 'CHANGED — inspect SOURCE_VERIFICATION.json' if state is False else 'unavailable') + '.', '']
    (out / 'FINAL_REPORT.md').write_text('\n'.join(lines))
    table = '<table><thead><tr>' + ''.join('<th>' + html.escape(k) + '</th>' for k in fieldnames) + '</tr></thead><tbody>'
    for row in rows: table += '<tr>' + ''.join('<td>' + html.escape(str(row.get(k, ''))) + '</td>' for k in fieldnames) + '</tr>'
    table += '</tbody></table>'
    (out / 'FINAL_REPORT.html').write_text('<!doctype html><meta charset="utf-8"><title>Jira benchmark report</title><style>body{font:16px system-ui;margin:3em;max-width:1400px;color:#172033}table{border-collapse:collapse;font-size:13px}td,th{padding:9px;border:1px solid #ccd3dc;text-align:left}th{background:#edf2f7}pre{white-space:pre-wrap;line-height:1.5;font:15px system-ui}</style><h1>Jira benchmark results</h1>'+table+'<pre>'+html.escape('\n'.join(lines))+'</pre>')
    artifacts = ['# Artifact inventory', '', 'Files are relative to the closed run directory. Hashes are in MANIFEST.json.', '']
    for p in sorted(root.rglob('*')):
        if p.is_file() and not p.is_symlink() and not p.is_relative_to(out) and p.suffix in ('.patch', '.md', '.xml'):
            artifacts.append('- ' + str(p.relative_to(root)))
    (out / 'ARTIFACTS.md').write_text('\n'.join(artifacts) + '\n')
    archive = archive_evidence(root, out)
    print(out / 'FINAL_REPORT.html'); print(archive)
    return out

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--results', required=True, type=Path)
    p.add_argument('--run-audits', action='store_true')
    a = p.parse_args(); finalize(a.results, a.run_audits)
