"""Additional tests to increase repository coverage to 100%.

These tests exercise internal helpers, the algorithm registry, and the generic
``*ALGO|N`` query handling.
"""

import pytest
import networkx as nx

from nxcypher import Cypher
from nxcypher.algorithms import register_algorithm, get_algorithm
from nxcypher.model import ReturnItem, NodePattern, RelPattern


def test_algorithm_registry_register_and_lookup():
    # Register a dummy algorithm and verify lookup works (case‑insensitive).
    def dummy_algo(g, s, t, p):
        return [["dummy"]]

    register_algorithm("DUMMY", dummy_algo)
    assert get_algorithm("dummy") is dummy_algo
    # Unknown algorithm should raise KeyError.
    with pytest.raises(KeyError):
        get_algorithm("nonexistent")


def test_generic_algo_query_uses_registered_algorithm():
    G = nx.MultiDiGraph()
    G.add_edge("a", "b")
    G.add_edge("b", "c")
    engine = Cypher(G)

    # Register a simple algorithm that always returns a fixed path.
    def fixed_algo(g, s, t, p):
        return [["a", "b"]]

    register_algorithm("FIXED", fixed_algo)
    rows = list(
        engine.run(
            "MATCH (source), (target)\n"
            "WITH source, target\n"
            "MATCH path=(source)-[*FIXED|1]->(target)\n"
            "RETURN path;"
        )
    )
    assert rows == [{"path": ["a", "b"]}]


def test_eval_expr_operations():
    engine = Cypher(nx.MultiDiGraph())
    row = {}
    # Literal
    assert engine._eval_expr(("lit", 5), row) == 5
    # Binary addition
    expr = ("bin", "+", ("lit", 2), ("lit", 3))
    assert engine._eval_expr(expr, row) == 5
    # Unary negation
    expr = ("un", "-", ("lit", 4))
    assert engine._eval_expr(expr, row) == -4
    # Logical AND
    expr = ("bin", "AND", ("lit", True), ("lit", False))
    assert engine._eval_expr(expr, row) is False


def test_project_row_alias_and_name():
    G = nx.MultiDiGraph()
    G.add_node(1, labels={"Person"}, name="Alice")
    engine = Cypher(G)
    # ReturnItem with explicit alias
    ri_alias = ReturnItem(expr=("prop", "a", "name"), alias="src")
    # ReturnItem without alias – name derived from expression
    ri_no_alias = ReturnItem(expr=("prop", "a", "name"), alias=None)
    row = {"a": ("node", 1)}
    result = engine._project_row([ri_alias, ri_no_alias], row)
    assert result["src"] == "Alice"
    # The derived key should be "a.name"
    assert result["a.name"] == "Alice"


def test_node_and_rel_ok_helpers():
    G = nx.MultiDiGraph()
    G.add_node(1, labels={"Person"}, age=30)
    G.add_node(2, labels={"Person"})
    G.add_edge(1, 2, key=0, type="KNOWS", since=2020)
    engine = Cypher(G)
    # Node pattern matches
    npat_match = NodePattern(var="a", labels=("Person",), properties={"age": 30})
    assert engine._node_ok(1, npat_match) is True
    npat_no_match = NodePattern(var="a", labels=("Person",), properties={"age": 31})
    assert engine._node_ok(1, npat_no_match) is False
    # Relationship pattern matches
    rpat_match = RelPattern(var="r", types=("KNOWS",), properties={"since": 2020})
    assert engine._rel_ok(1, 2, 0, rpat_match) is True
    rpat_no_match = RelPattern(var="r", types=("FRIEND",), properties={})
    assert engine._rel_ok(1, 2, 0, rpat_no_match) is False