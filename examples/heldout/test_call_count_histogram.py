import importlib
import pkgutil
from orchestrator.pkg.stats import FunctionCallFrequency


def find_histogram():
    package = importlib.import_module('orchestrator.pkg')
    for entry in pkgutil.iter_modules(package.__path__):
        try:
            module = importlib.import_module(f'orchestrator.pkg.{entry.name}')
        except ImportError:
            continue
        fn = getattr(module, 'call_count_histogram', None)
        if callable(fn):
            return fn
    raise AssertionError('call_count_histogram not found in orchestrator.pkg')


def test_empty_repeated_and_preservation():
    fn = find_histogram()
    assert fn([]) == {}
    values = [FunctionCallFrequency(node_id=f'py:f{i}', name=f'f{i}', call_count=c)
              for i,c in enumerate([0, 8, 2, 8, 0, 8])]
    before = [(id(x), x.node_id, x.name, x.call_count) for x in values]
    result = fn(values)
    assert result == {0:2, 8:3, 2:1}
    assert all(type(k) is int and type(v) is int for k,v in result.items())
    assert [(id(x), x.node_id, x.name, x.call_count) for x in values] == before
    assert fn([values[1]]) == {8:1}
