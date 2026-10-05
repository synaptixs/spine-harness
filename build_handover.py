#!/usr/bin/env python3
"""Build the external handover from an explicit allowlist, never the workspace tree."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
NAME = "spec-kit-vs-spine-codex-harness"
VERSION = "2026-09-30-v6"
FILES = (
    "setup.sh", "harness_config.py", "run_comparison.py", "speckit_codex.py",
    "speckit_claude.py", "spine_pkg.py", "spine_intake.py", "codex_llm.py",
    "codex_protocol.py", "codex_usage.py", "gpt6_shim.py", "heldout_fix.py",
    "constitution.md", "summarize.py", "report_usage.py", "test_codex_backend.py",
    "test_report_usage.py", ".gitignore", "scenario_catalog.py", "scenarios.py",
    "report_results.py", "model_report.py", "test_scenarios.py", "examples/scenarios.json",
    "examples/heldout/test_call_count_range.py", "examples/heldout/test_call_count_histogram.py",
)
FILES += ("jira_import.py", "project_adapter.py", "project_benchmark.py", "report_project.py", "test_jira_benchmark.py", "profiles/ontomesh.json")
FILES += ("catalog/expanded.json", "catalog/INDEX.md", "profiles/pilot.env") + tuple(
    f"catalog/heldout/test_{row['key'][4:-2].lower().replace('-', '_')}.py"
    for row in json.loads((ROOT / "catalog/expanded.json").read_text())["scenarios"]
)
DOCS = ("README.md", "QUICKSTART.md", "CODEX_RUN.md", "METHODOLOGY.md", "SCENARIOS.md", "JIRA_BENCHMARK.md", "env.example")


def main():
    dist = ROOT / "dist"
    stage = dist / NAME
    stage.mkdir(parents=True, exist_ok=True)
    expected = set(FILES + DOCS) | {"MANIFEST.json", "SHA256SUMS"}
    extras = {str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()} - expected
    if extras:
        raise SystemExit(f"Unexpected staging entries; inspect before packaging: {extras}")
    for name in FILES:
        (stage / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, stage / name)
    for name in DOCS:
        shutil.copy2(ROOT / "distribution" / name, stage / name)
    hashes = {}
    for name in sorted(FILES + DOCS):
        data = (stage / name).read_bytes()
        for marker in (b"/Users/", b"/private/tmp/spineharness-", b".claude/tools/", b"falcon"):
            if marker in data:
                raise SystemExit(f"Machine-specific marker in {name}: {marker!r}")
        if re.search(rb"\bsk-[A-Za-z0-9_-]{20,}", data):
            raise SystemExit(f"Possible credential in {name}")
        hashes[name] = hashlib.sha256(data).hexdigest()
    manifest = {
        "package": NAME, "version": VERSION, "default_backend": "Codex subscription adapter",
        "target_commit": "bd16dbb7d2451bfaffa94c02946972050e23a610",
        "spine_ref": "v3.52.0", "spine_commit": "6c0454bac2dbb539665402d31e57e763db2d206a",
        "speckit_ref": "v1.0.11", "held_out_suite": "a6ac7c34",
        "tested_codex_cli": "0.157.0", "tested_python": "3.12", "tested_uv": "0.8.0",
        "includes_credentials": False, "includes_results": False, "includes_spine_repository": False,
        "scenario_catalog_schema": 1, "default_scenarios": 33, "additional_scenarios": 30, "supported_scenarios": "Graded reference scenarios plus experimental Python project token-only adapter",
        "validation_scope": "Local tests and extracted-package dry run; no new live model run for this release",
        "sha256": hashes,
    }
    (stage / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    hashes["MANIFEST.json"] = hashlib.sha256((stage / "MANIFEST.json").read_bytes()).hexdigest()
    (stage / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())))
    archive = dist / f"{NAME}-{VERSION}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for name in sorted(expected):
            zipped.write(stage / name, f"{NAME}/{name}")
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise SystemExit("Archive integrity check failed")
        if set(zipped.namelist()) != {f"{NAME}/{name}" for name in expected}:
            raise SystemExit("Archive file inventory mismatch")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = archive.with_suffix(".zip.sha256")
    checksum.write_text(f"{digest}  {archive.name}\n")
    print(json.dumps({"archive": str(archive), "bytes": archive.stat().st_size,
                      "files": len(expected), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
