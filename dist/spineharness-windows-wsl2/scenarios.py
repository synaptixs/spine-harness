#!/usr/bin/env python3
"""Inspect or validate scenarios without making model calls (use the Spine uv environment)."""
import argparse
import json
from pathlib import Path
import sys
import harness_config as C
from scenario_catalog import configure, fingerprint
import heldout_fix


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=('list','validate','snapshot'))
    ap.add_argument('--tree',choices=('target','spine'),default='target')
    a=ap.parse_args()
    C.use_tree(C.TARGET_DIR if a.tree=='target' else C.SPINE_CODE_DIR)
    import codegen_benchmark as cb
    suite=heldout_fix.apply(cb)
    if a.action=='list':
        keys=[t.key for t in cb.TICKETS]
        if C.SCENARIO_FILE:
            from scenario_catalog import load_catalog
            keys += [r['key'] for r in load_catalog(C.SCENARIO_FILE)[0]]
        configure(cb,keys,C.SCENARIO_FILE,C.TARGET_DIR)
        for t in cb.TICKETS:
            print(f'{t.key}\t{t.kind}\t{t.spec["title"]}')
        return
    custom=configure(cb,C.TICKETS,C.SCENARIO_FILE,C.TARGET_DIR)
    result={'tickets':C.TICKETS,'scenario_fingerprint':fingerprint(cb.TICKETS),
            'python_version':sys.version.split()[0],
            'stock_held_out_suite':suite,'custom_catalog':custom,
            'scenarios':[{'key':t.key,'kind':t.kind,'spec':t.spec,'must_edit':t.must_edit} for t in cb.TICKETS]}
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    try: main()
    except (ValueError,OSError,SyntaxError) as exc: sys.exit(f'Scenario validation failed: {exc}')
