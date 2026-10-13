"""Render model provenance from saved benchmark configuration and measurements."""
from collections import Counter


def model_section(config, groups, usage):
    """groups contains (workflow, requested model, saved measurement rows)."""
    effort = config.get('model_reasoning_effort', config.get('reasoning_effort'))
    warnings = []
    lines = ['## Models used in benchmark runs', '',
             '| Workflow / component | Requested model | Model IDs in saved measurements | Saved measurements | Reasoning effort |',
             '|---|---|---|---:|---|']
    for label, requested, rows in groups:
        counts = Counter(row.get('model') or 'unknown (not recorded)' for row in rows)
        recorded = ', '.join(f'`{name}` ({n})' for name, n in sorted(counts.items())) or 'No saved measurements'
        efforts = sorted({r['reasoning_effort'] for r in rows if r.get('reasoning_effort')})
        reasoning = ', '.join(efforts) or 'unknown (not recorded)'
        if effort and not efforts and not requested.startswith('claude'):
            reasoning = f'{effort} (configured; absent from measurement rows)'
        elif efforts and any(not r.get('reasoning_effort') for r in rows):
            reasoning += ' (some rows missing)'
        lines.append(f'| {label} | `{requested}` | {recorded} | {len(rows)} | {reasoning} |')
        if any(name != requested and not name.startswith('unknown (') for name in counts):
            warnings.append(f'**Model mismatch:** {label} measurements differ from requested `{requested}`; review before interpreting comparisons.')
    for warning in warnings:
        lines += ['', warning]
    lines += ['', 'Saved measurement counts include incomplete attempts; completed counts are reported separately. '
              'Requested settings come from the frozen experiment/protocol, not the current environment. '
              'Model IDs in summaries identify the recorded runner selection; exported response ledgers provide additional execution evidence.', '']
    models = usage.get('models', {})
    if models:
        lines += ['**Model IDs in exported Codex response records:** ' + '; '.join(
            f'`{m}` — {u["requests"]:,} responses' for m, u in sorted(models.items())) + '.', '']
    else:
        lines += ['**Response-record evidence:** no exported Codex response ledger; actual response model identity is unverified.', '']
    lines += ['Only the benchmark records are included here. Models used to coordinate the work or write this report, '
              'and models appearing only in the historical reference report, are not benchmark measurements.', '']
    return lines
