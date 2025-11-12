import networkx as nx
from nxcypher import Cypher

def test_kshortest_query():
    """Validate the custom ``*KSHORTEST`` query syntax via Cypher.run()."""
    # Simple graph: a line a-b-c-d and a shortcut a-d
    G = nx.MultiDiGraph()
    G.add_edge('a', 'b')
    G.add_edge('b', 'c')
    G.add_edge('c', 'd')
    G.add_edge('a', 'd')
    engine = Cypher(G)

    query = (
        "MATCH (source), (target)\n"
        "WITH source, target\n"
        "MATCH path=(source)-[*KSHORTEST|3]->(target)\n"
        "RETURN path;"
    )
    rows = list(engine.run(query))
    # Extract the node sequences from the returned ``path`` values.
    paths = [row['path'] for row in rows]
    # The expected paths (order not guaranteed).
    expected = [['a', 'd'], ['a', 'b', 'c', 'd']]
    for exp in expected:
        assert exp in paths
    # Only two distinct paths exist in this graph.
    assert len(paths) == 2
