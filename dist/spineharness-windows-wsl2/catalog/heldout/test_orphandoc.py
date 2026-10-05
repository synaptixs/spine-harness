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
    args = (graph([]),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.documentation_gaps"), "orphan_documents")
    assert function(*args) == []
    assert args == before

def test_case_1():
    args = (graph(['d','bound','f','ext','m'], [('bound','f',EdgeKind.MENTIONS),('d','ext',EdgeKind.MENTIONS),('d','m',EdgeKind.MENTIONS)],d={'kind':NodeKind.DOC},bound={'kind':NodeKind.DOC},ext={'external':True},m={'kind':NodeKind.MODULE}),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.documentation_gaps"), "orphan_documents")
    assert function(*args) == ['d']
    assert args == before

def test_case_2():
    args = (graph(['d','f'], [('d','f')],d={'kind':NodeKind.DOC}),)
    before = copy.deepcopy(args)
    function = getattr(importlib.import_module("orchestrator.pkg.documentation_gaps"), "orphan_documents")
    assert function(*args) == ['d']
    assert args == before

