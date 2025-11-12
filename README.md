# nxcypher

A minimal, extensible Python module to parse a practical subset of openCypher and execute queries against a `networkx` graph.

## Features (initial subset)
- `MATCH` linear patterns with directed relationships: `(a:Label {k: v})-[:TYPE]->(b)`
- Optional multiple labels and properties on nodes and relationships
- `WHERE` with comparisons, boolean ops, and property access (e.g., `a.name = "Alice" AND b.age > 30`)
- `RETURN` projections with aliases
- `ORDER BY`, `SKIP`, `LIMIT`
- Simple aggregations: `count(*)`

> This is a foundation to grow toward broader openCypher compatibility.

## Install
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Quick start
```python
import networkx as nx
from nxcypher import Cypher

G = nx.MultiDiGraph()
G.add_node(1, labels={"Person"}, name="Alice", age=35)
G.add_node(2, labels={"Person"}, name="Bob", age=29)
G.add_edge(1, 2, key=0, type="KNOWS", since=2020)

engine = Cypher(G)
rows = list(engine.run('MATCH (a:Person)-[r:KNOWS]->(b:Person) WHERE a.age > 30 RETURN a.name AS src, b.name AS dst ORDER BY dst LIMIT 10'))
print(rows)  # [{'src': 'Alice', 'dst': 'Bob'}]
```

## Tests
```bash
pytest -q
```
