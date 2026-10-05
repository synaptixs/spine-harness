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
    args = ([],)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.provenance_ranges"), "merge_source_ranges")
    assert function(*args) == []
    assert args == before

def test_case_1():
    args = ([Provenance('a',4,6),Provenance('a',1,3),Provenance('a',10),Provenance('a',2,5,'other'),Provenance('b',1)],)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.provenance_ranges"), "merge_source_ranges")
    assert function(*args) == [('','a',1,6),('','a',10,10),('','b',1,1),('other','a',2,5)]
    assert args == before

def test_case_2():
    args = ([Provenance('a',3,2)],)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.provenance_ranges"), "merge_source_ranges")
    with pytest.raises(ValueError):
        function(*args)
    assert args == before

def test_case_3():
    args = ([Provenance('a',0)],)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.provenance_ranges"), "merge_source_ranges")
    with pytest.raises(ValueError):
        function(*args)
    assert args == before

