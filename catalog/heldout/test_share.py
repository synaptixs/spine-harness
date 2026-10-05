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
    args = (freq(),0)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "top_call_share")
    assert function(*args) == 0.0
    assert args == before

def test_case_1():
    args = (freq(('a','a',6),('b','b',2),('c','c',2)),1)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "top_call_share")
    assert function(*args) == 0.6
    assert args == before

def test_case_2():
    args = (freq(('a','a',6),('b','b',2),('c','c',2)),2)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "top_call_share")
    assert function(*args) == 0.8
    assert args == before

def test_case_3():
    args = (freq(('a','a',2)),9)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "top_call_share")
    assert function(*args) == 1.0
    assert args == before

def test_case_4():
    args = (freq(('a','a',0)),1)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "top_call_share")
    assert function(*args) == 0.0
    assert args == before

def test_case_5():
    args = (freq(),-1)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "top_call_share")
    with pytest.raises(ValueError):
        function(*args)
    assert args == before

