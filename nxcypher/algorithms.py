"""Algorithm registry and built‑in path‑finding helpers.

The goal of this module is to decouple graph algorithms from the core
``Cypher`` executor.  Algorithms can be registered at import time or by third‑
party plugins.  The executor looks up an algorithm by name and calls it with the
graph instance and the parameters extracted from the ``*ALGO|N`` syntax used in
Cypher queries.

Only a few algorithms are provided out‑of‑the‑box – they are simple wrappers
around NetworkX utilities:

* ``kshortest`` – returns up to *k* simple paths (the original implementation).
* ``bfs`` – breadth‑first search returning all nodes reachable from ``source``
  up to depth *k*.
* ``allshortest`` – all shortest paths between ``source`` and ``target``.
* ``wshortest`` – weighted shortest path using Dijkstra's algorithm.

Plugins can register additional algorithms via :func:`register_algorithm`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple
import networkx as nx

# ---------------------------------------------------------------------------
# Registry infrastructure
# ---------------------------------------------------------------------------
_registry: Dict[str, Callable[[nx.Graph, Any, Any, int], List[List[Any]]]] = {}


def register_algorithm(name: str, func: Callable[[nx.Graph, Any, Any, int], List[List[Any]]]) -> None:
    """Register a new algorithm.

    ``func`` must accept ``(graph, source, target, param)`` and return a list of
    paths, where each path is a list of node identifiers.
    """
    _registry[name.upper()] = func


def get_algorithm(name: str) -> Callable[[nx.Graph, Any, Any, int], List[List[Any]]]:
    """Retrieve a registered algorithm or raise ``KeyError`` if unknown."""
    return _registry[name.upper()]


# ---------------------------------------------------------------------------
# Built‑in algorithms
# ---------------------------------------------------------------------------
def _kshortest_impl(graph: nx.Graph, source: Any, target: Any, k: int) -> List[List[Any]]:
    """Return up to *k* simple paths between ``source`` and ``target``.

    This mirrors the original ``Cypher.kshortest_paths`` implementation.
    """
    paths = list(nx.all_simple_paths(graph, source, target))
    paths.sort(key=len)
    return paths[:k]


def _bfs_impl(graph: nx.Graph, source: Any, target: Any, depth: int) -> List[List[Any]]:
    """Bread‑first search up to ``depth`` levels.

    Returns a list of node sequences representing the traversal tree from the
    ``source``.  ``target`` is ignored for BFS – it is kept in the signature for
    compatibility with the registry.
    """
    visited = {source}
    frontier = [(source, [source])]
    result: List[List[Any]] = []
    while frontier:
        node, path = frontier.pop(0)
        if len(path) - 1 > depth:
            continue
        result.append(path)
        for nbr in graph.neighbors(node):
            if nbr not in visited:
                visited.add(nbr)
                frontier.append((nbr, path + [nbr]))
    return result


def _allshortest_impl(graph: nx.Graph, source: Any, target: Any, _: int) -> List[List[Any]]:
    """All shortest paths between ``source`` and ``target``.

    The ``param`` argument is ignored – it is present for a uniform call signature.
    """
    return list(nx.all_shortest_paths(graph, source, target))


def _wshortest_impl(graph: nx.Graph, source: Any, target: Any, _: int) -> List[List[Any]]:
    """Weighted shortest path using Dijkstra's algorithm.

    Returns a single shortest path wrapped in a list for consistency.
    """
    try:
        path = nx.dijkstra_path(graph, source, target)
        return [path]
    except nx.NetworkXNoPath:
        return []


# Register built‑in algorithms under their canonical names.
register_algorithm("KSHORTEST", _kshortest_impl)
register_algorithm("BFS", _bfs_impl)
register_algorithm("ALLSHORTEST", _allshortest_impl)
register_algorithm("WSHORTEST", _wshortest_impl)
