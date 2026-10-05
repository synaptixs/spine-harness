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
    args = (DBSchema('db'),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.schema"), "foreign_key_errors")
    assert function(*args) == []
    assert args == before

def test_case_1():
    args = (DBSchema('db',(DBTable('a',(DBColumn('id'),),(ForeignKey('x','ghost','id'),ForeignKey('id','b','bad'))),DBTable('b',(DBColumn('id'),)))),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.schema"), "foreign_key_errors")
    assert function(*args) == [('a','id','missing-ref-column'),('a','x','missing-local-column'),('a','x','missing-table')]
    assert args == before

def test_case_2():
    args = (DBSchema('db',(DBTable('a',(DBColumn('id'),),(ForeignKey('id','a',''),)),)),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.schema"), "foreign_key_errors")
    assert function(*args) == []
    assert args == before

