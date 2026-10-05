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
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "merge_call_frequencies")
    assert function(*args) == []
    assert args == before

def test_case_1():
    args = ([freq(('b','B',2),('a','A',1)),freq(('a','A',4))],)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "merge_call_frequencies")
    assert function(*args) == freq(('a','A',5),('b','B',2))
    assert args == before

def test_case_2():
    args = ([freq(('a','A',1)),freq(('a','Other',2))],)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "merge_call_frequencies")
    with pytest.raises(ValueError):
        function(*args)
    assert args == before

def test_case_3():
    args = ([[],[]],)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.stats"), "merge_call_frequencies")
    assert function(*args) == []
    assert args == before

def test_result_records_do_not_alias_inputs():
    records = freq(('a', 'A', 2))
    function = getattr(importlib.import_module('orchestrator.pkg.stats'), 'merge_call_frequencies')
    output = function([records])
    assert output == records
    assert output[0] is not records[0]
    output[0].call_count = 99
    assert records[0].call_count == 2
