"""Freeze deterministic Spine PKG facts as one implementation context.

Run this with the pinned Spine tools interpreter. It makes no model call and
does not infer facts from filenames; focus paths select already extracted facts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def render(repo: Path, focus: list[str], baseline: str) -> tuple[str, dict]:
    from orchestrator.pkg.extractor import RepoCodeExtractor

    if git(repo, "rev-parse", "HEAD") != baseline:
        raise ValueError("PKG source is not at the frozen baseline")
    if git(repo, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("PKG source clone must be clean")
    if not focus or any(Path(rel).is_absolute() or ".." in Path(rel).parts for rel in focus):
        raise ValueError("Focus paths must be repository-relative files")
    for rel in focus:
        if not (repo / rel).is_file():
            raise ValueError(f"Focus file is absent: {rel}")
    extractor = RepoCodeExtractor()
    facts = extractor.extract(repo)
    nodes = sorted((node for node in facts.nodes if node.provenance and node.provenance.file in focus),
                   key=lambda node: (node.provenance.file, node.provenance.line, node.id))
    if not nodes:
        raise ValueError("Spine PKG found no grounded nodes in focus files")
    ids = {node.id for node in nodes}
    edges = sorted((edge for edge in facts.edges if edge.src in ids or edge.dst in ids),
                   key=lambda edge: (edge.src, edge.dst, edge.kind.value, str(edge.provenance)))
    lines = ["# Spine + PKG context", "",
             f"Spine PKG extracted the pinned application commit `{baseline}`.",
             f"Full graph: {len(facts.nodes)} nodes, {len(facts.edges)} edges; "
             f"{len(extractor.skipped)} skipped files.",
             f"Focus: {len(nodes)} grounded nodes and {len(edges)} touching edges from "
             f"{len(focus)} selected files. These are the complete selected sets.", "",
             "## Grounded symbols", ""]
    lines.extend(f"- `{node.id}` ({node.kind.value}) — `{node.provenance.file}:{node.provenance.line}`"
                 for node in nodes)
    lines.extend(["", "## Relations touching those symbols", ""])
    lines.extend(f"- `{edge.src}` —{edge.kind.value}→ `{edge.dst}`"
                 + (f" (`{edge.provenance}`)" if edge.provenance else "") for edge in edges)
    lines.extend(["", "The graph describes existing code. Missing edges are not evidence that a "
                  "runtime call is impossible; inspect the source before editing.", ""])
    payload = {
        "graph_nodes": len(facts.nodes), "graph_edges": len(facts.edges),
        "skipped_files": sorted(extractor.skipped),
        "focus_files": {rel: hashlib.sha256((repo / rel).read_bytes()).hexdigest() for rel in sorted(focus)},
        "selected_nodes": len(nodes), "selected_edges": len(edges),
    }
    return "\n".join(lines), payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--focus", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    import orchestrator

    spine_version = orchestrator.__version__
    tools_root = Path(orchestrator.__file__).resolve().parents[2]
    tools_commit = git(tools_root, "rev-parse", "HEAD")

    text, evidence = render(args.repo.resolve(), args.focus, args.baseline)
    if len(text.encode()) > 65536:
        raise ValueError("PKG context exceeds 64 KiB; review scope instead of silently clipping")
    output = {
        "arm": "spine-pkg", "task_id": args.task_id,
        "baseline_commit": args.baseline,
        "producer": f"Spine {spine_version} ({tools_commit}) PKG extractor",
        "readiness": "review_pending", "text": text,
        "evidence": evidence | {
            "spine_commit": tools_commit,
            "producer_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("Refusing to overwrite an existing context artifact")
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(args.output)


if __name__ == "__main__":
    main()
