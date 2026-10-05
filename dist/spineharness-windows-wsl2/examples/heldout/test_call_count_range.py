from orchestrator.pkg.stats import FunctionCallFrequency, call_count_range


def frequencies(counts):
    return [FunctionCallFrequency(node_id=f'py:f{i}', name=f'f{i}', call_count=c)
            for i,c in enumerate(counts)]


def test_empty_and_singleton():
    assert call_count_range([]) == 0
    assert call_count_range(frequencies([7])) == 0


def test_range_and_preservation():
    values = frequencies([9, 0, 9, 4, 2])
    before = [(id(x), x.node_id, x.name, x.call_count) for x in values]
    result = call_count_range(values)
    assert result == 9 and type(result) is int
    assert [(id(x), x.node_id, x.name, x.call_count) for x in values] == before
    assert call_count_range(frequencies([5, 5])) == 0
    assert call_count_range(frequencies([10**9, 1])) == 10**9-1
