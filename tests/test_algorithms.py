import networkx as nx
from nxcypher import Cypher


def _run_query(engine: Cypher, algo_name: str, param: int):
    """Helper to build and execute a generic *ALGO|N* query.

    The query follows the pattern used in the existing K‑shortest test.
    """
    query = (
        "MATCH (source), (target)\n"
        "WITH source, target\n"
        f"MATCH path=(source)-[*{algo_name}|{param}]->(target)\n"
        "RETURN path;"
    )
    return list(engine.run(query))


def test_bfs_algorithm():
    """BFS should return all node sequences up to the given depth.

    The graph is a simple line a‑b‑c‑d with an additional direct edge a‑d.
    Depth 2 from the first node (a) to the last node (d) yields the paths:
    ['a'], ['a', 'b'], ['a', 'd'], ['a', 'b', 'c'].
    """
    G = nx.MultiDiGraph()
    G.add_edge('a', 'b')
    G.add_edge('b', 'c')
    G.add_edge('c', 'd')
    G.add_edge('a', 'd')
    engine = Cypher(G)
    rows = _run_query(engine, "BFS", 2)
    paths = [row['path'] for row in rows]
    expected = [['a'], ['a', 'b'], ['a', 'd'], ['a', 'b', 'c']]
    for exp in expected:
        assert exp in paths
    # No extra paths beyond the expected set.
    assert len(paths) == len(expected)


def test_allshortest_algorithm():
    """ALLSHORTEST should return all shortest paths between source and target.

    In the graph below the direct edge a‑d is the unique shortest path.
    """
    G = nx.MultiDiGraph()
    G.add_edge('a', 'b')
    G.add_edge('b', 'c')
    G.add_edge('c', 'd')
    G.add_edge('a', 'd')
    engine = Cypher(G)
    rows = _run_query(engine, "ALLSHORTEST", 0)
    paths = [row['path'] for row in rows]
    assert paths == [['a', 'd']]


def test_wshortest_algorithm():
    """WSHORTEST should return the weighted shortest path.

    Edge weights are set so that the indirect path a‑b‑c‑d (total weight 3) is
    shorter than the direct edge a‑d (weight 10).
    """
    G = nx.MultiDiGraph()
    G.add_edge('a', 'b', weight=1)
    G.add_edge('b', 'c', weight=1)
    G.add_edge('c', 'd', weight=1)
    G.add_edge('a', 'd', weight=10)
    engine = Cypher(G)
    rows = _run_query(engine, "WSHORTEST", 0)
    paths = [row['path'] for row in rows]
    assert paths == [['a', 'b', 'c', 'd']]
