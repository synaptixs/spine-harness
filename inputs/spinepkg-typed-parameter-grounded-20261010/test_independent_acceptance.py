from pathlib import Path

from spine import EdgeKind, RepoCodeExtractor


def test_annotated_parameter_call_is_grounded_without_guessing(tmp_path: Path) -> None:
    (tmp_path / "service.py").write_text(
        "class Service:\n"
        "    def ping(self):\n"
        "        return 1\n\n"
        "def checked(item: Service):\n"
        "    return item.ping()\n\n"
        "def unknown(item):\n"
        "    return item.ping()\n",
        encoding="utf-8",
    )
    batch = RepoCodeExtractor().extract(tmp_path)
    calls = {(edge.src, edge.dst) for edge in batch.edges if edge.kind == EdgeKind.CALLS}
    assert ("py:service.checked", "py:service.Service.ping") in calls
    assert ("py:service.unknown", "py:service.Service.ping") not in calls
    grounded = [
        edge for edge in batch.edges
        if edge.kind == EdgeKind.CALLS
        and edge.src == "py:service.checked"
        and edge.dst == "py:service.Service.ping"
    ]
    assert len(grounded) == 1
    assert grounded[0].provenance.file == "service.py"
    assert grounded[0].provenance.line == 6
    repeat = RepoCodeExtractor().extract(tmp_path)
    assert sorted((e.src, e.dst, e.kind.value, e.provenance.file, e.provenance.line) for e in batch.edges) == sorted(
        (e.src, e.dst, e.kind.value, e.provenance.file, e.provenance.line) for e in repeat.edges
    )
