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
    args = (freq(),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "median_call_count")
    assert function(*args) == 0
    assert args == before

def test_case_1():
    args = (freq(('a','a',9),('b','b',1),('c','c',4),('d','d',2)),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "median_call_count")
    assert function(*args) == 2
    assert args == before

def test_case_2():
    args = (freq(('a','a',0),('a','a',7),('b','b',3)),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "median_call_count")
    assert function(*args) == 3
    assert args == before

def test_case_3():
    args = (freq(('a','a',8)),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "median_call_count")
    assert function(*args) == 8
    assert args == before

