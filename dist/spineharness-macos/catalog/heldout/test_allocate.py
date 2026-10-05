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
    args = (freq(),3)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "allocate_call_budget")
    assert function(*args) == {}
    assert args == before

def test_case_1():
    args = (freq(('b','B',1),('a','A',1),('c','C',1)),2)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "allocate_call_budget")
    assert function(*args) == {'a':1,'b':1,'c':0}
    assert args == before

def test_case_2():
    args = (freq(('a','A',5),('b','B',3),('c','C',2)),7)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "allocate_call_budget")
    assert function(*args) == {'a':4,'b':2,'c':1}
    assert args == before

def test_case_3():
    args = (freq(('a','A',0),('b','B',0)),9)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "allocate_call_budget")
    assert function(*args) == {'a':0,'b':0}
    assert args == before

def test_case_4():
    args = (freq(('a','A',10**20),('b','B',10**20+1)),1)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "allocate_call_budget")
    assert function(*args) == {'a':0,'b':1}
    assert args == before

def test_case_5():
    args = (freq(),-1)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "allocate_call_budget")
    with pytest.raises(ValueError):
        function(*args)
    assert args == before

