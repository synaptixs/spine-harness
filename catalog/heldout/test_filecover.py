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
    args = ([],)
    before = copy.deepcopy(args)
    function = importlib.import_module("orchestrator.pkg.file_coverage").grounded_file_counts
    assert function(*args) == {}
    assert args == before

def test_case_1():
    args = ([node('a'),node('a'),node('b'),node('x',external=True),node('y',file=None),node('a',repo='r')],)
    before = copy.deepcopy(args)
    function = importlib.import_module("orchestrator.pkg.file_coverage").grounded_file_counts
    assert function(*args) == {('','a.py'):2,('r','a.py'):1}
    assert args == before

def test_case_2():
    args = ([node('a',file='b.py'),node('a')],)
    before = copy.deepcopy(args)
    function = importlib.import_module("orchestrator.pkg.file_coverage").grounded_file_counts
    assert function(*args) == {('','a.py'):1,('','b.py'):1}
    assert args == before

