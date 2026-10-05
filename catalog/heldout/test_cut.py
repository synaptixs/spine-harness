import copy
import importlib

from orchestrator.pkg.facts import Edge, EdgeKind, FactBatch, Node, NodeKind, Provenance
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
    args = (graph([]),{'a'})
    before = copy.deepcopy(args)
    function = importlib.import_module("orchestrator.pkg.dependency_cut").outgoing_boundary
    assert function(*args) == []
    assert args == before

def test_case_1():
    args = (graph(['a','b','c','e'], [('a','b'),('b','c',EdgeKind.IMPORTS),('c','a'),('a','e',EdgeKind.READS),('a','ghost')],e={'external':True}),{'a','b','missing'})
    before = copy.deepcopy(args)
    function = importlib.import_module("orchestrator.pkg.dependency_cut").outgoing_boundary
    assert function(*args) == [('a','e','READS'),('b','c','IMPORTS')]
    assert args == before

def test_case_2():
    args = (graph(['a'], [('a','a')]),{'a'})
    before = copy.deepcopy(args)
    function = importlib.import_module("orchestrator.pkg.dependency_cut").outgoing_boundary
    assert function(*args) == []
    assert args == before

