import networkx as nx
from nxcypher import Cypher


def test_simple_match_where_return():
    G = nx.MultiDiGraph()
    G.add_node(1, labels={"Person"}, name="Alice", age=35)
    G.add_node(2, labels={"Person"}, name="Bob", age=29)
    G.add_node(3, labels={"Person"}, name="Carol", age=40)
    G.add_edge(1, 2, key=0, type="KNOWS", since=2020)
    G.add_edge(1, 3, key=0, type="KNOWS", since=2010)

    engine = Cypher(G)
    q = "MATCH (a:Person)-[r:KNOWS]->(b:Person) WHERE a.age > 30 RETURN a.name AS src, b.name AS dst ORDER BY dst"
    rows = list(engine.run(q))
    assert rows == [{"src": "Alice", "dst": "Bob"}, {"src": "Alice", "dst": "Carol"}]
