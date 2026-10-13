"""The corrected held-out test for NEW-DRIFTMD-1, applied to both tools before any run.

The measured trees (target bd16dbb7, Spine v3.52.0) carry a held-out test no correct
solution can pass: it builds a stand-in finding (a str kind, no message) where the ticket
requires the real DocDriftFinding, so correct code fails on kind.value. Every run of every
tool failed the ticket on it. Spine fixed the test in a6ac7c34 (SSPN-97, PR #498).

The measured versions stay pinned, so cost, tokens and time reproduce the published runs; only
the judge changes. BODY below is that commit's suite verbatim (after the shared _HO_FIND
prelude, which is identical in all three trees). Each run's summary.json records
held_out_suite so a result says which judge graded it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

FIXED_IN = "a6ac7c34"
KEY = "NEW-DRIFTMD-1"
FILENAME = "test_driftmd_ho.py"
BODY = '\nimport re\n\nfrom orchestrator.pkg.docs import DocDriftFinding, MentionKind\n\n\ndef test_returns_non_empty_markdown_and_names_the_mentions():\n    fn = None\n    for pkg_name in ("orchestrator.pkg", "orchestrator.knowledge"):\n        try:\n            fn = _find(pkg_name, "render_drift_markdown")\n            break\n        except AssertionError:\n            continue\n    assert fn is not None, "render_drift_markdown not found"\n\n    # The real finding type, as the ticket requires. A hand-made stand-in (a str\n    # `kind`, no `message`) failed every correct solution on `kind.value` (B51).\n    kinds = list(MentionKind)\n    out = fn(\n        [\n            DocDriftFinding("Design", "missing_symbol", kinds[0], "not defined in code"),\n            DocDriftFinding("Design", "gone.py", kinds[-1], "file not found"),\n        ]\n    )\n    assert isinstance(out, str) and out.strip()\n    # Checked on the rendered text: `missing\\_symbol` is Markdown for missing_symbol.\n    text = re.sub(r"\\\\(.)", r"\\1", out)\n    assert "missing_symbol" in text and "gone.py" in text\n    assert "Design" in text\n'


def apply(cb: Any) -> str:
    """Swap the corrected suite into cb.TICKETS; return the suite id for the summary."""
    for i, t in enumerate(cb.TICKETS):
        if t.key != KEY:
            continue
        (name,) = t.held_out_tests
        if "DocDriftFinding(" in t.held_out_tests[name]:
            return "tree"  # the tree already carries the fix; nothing to replace
        cb.TICKETS[i] = replace(t, held_out_tests={FILENAME: cb._HO_FIND + BODY})
        return FIXED_IN
    return "tree"
