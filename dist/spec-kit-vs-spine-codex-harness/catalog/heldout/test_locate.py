import copy
import importlib
import pytest
from orchestrator.pkg.facts import FactBatch, Node, NodeKind, Edge, EdgeKind, Provenance
from orchestrator.pkg.schema import DBColumn, DBTable, DBSchema, ForeignKey
from orchestrator.pkg.stats import FunctionCallFrequency


def graph(ids, edges=(), **attrs):
    b = FactBatch()
    for ident in ids:
        options = attrs.get(ident, {})
        b.add_node(Node(ident, options.get('kind', NodeKind.FUNCTION), options.get('name', ident),
                        language=options.get('language', ''), provenance=options.get('provenance'),
                        external=options.get('external', False)))
    for item in edges:
        a, z, *kind = item
        b.add_edge(Edge(a, z, kind[0] if kind else EdgeKind.CALLS))
    return b


def freq(*values):
    return [FunctionCallFrequency(ident, name, count) for ident, name, count in values]


def node(ident, file='a.py', line=1, end=None, repo='', **kwargs):
    return Node(ident, NodeKind.FUNCTION, kwargs.get('name', ident),
                provenance=Provenance(file,line,end,repo) if file is not None else None,
                external=kwargs.get('external',False))


def test_case_0():
    args = ([], '', 'a.py',1)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.source_lookup"), "symbols_at_line")
    assert function(*args) == []
    assert args == before

def test_case_1():
    args = ([node('a',line=2,end=4),node('b',line=4),node('e',line=4,external=True),node('r',line=4,repo='r')],'','a.py',4)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.source_lookup"), "symbols_at_line")
    assert function(*args) == ['a','b']
    assert args == before

def test_case_2():
    args = ([node('a',line=2,end=4)],'','a.py',5)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.source_lookup"), "symbols_at_line")
    assert function(*args) == []
    assert args == before

def test_case_3():
    args = ([], '', 'a.py',0)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.source_lookup"), "symbols_at_line")
    with pytest.raises(ValueError):
        function(*args)
    assert args == before

