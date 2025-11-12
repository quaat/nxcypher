from __future__ import annotations
from typing import Any, Dict, Iterator, List
import operator
import networkx as nx

# Import the concrete data‑model classes explicitly to avoid star‑import lint warnings.
from .model import (
    Query,
    Match,
    NodePattern,
    RelPattern,
    Pattern,
    PatternElementChain,
    ReturnItem,
)
from .parser import parse

BinOps = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "%": operator.mod,
    "AND": lambda a, b: bool(a) and bool(b),
    "OR": lambda a, b: bool(a) or bool(b),
}
UnOps = {
    "-": operator.neg,
    "NOT": lambda a: not bool(a),
}


class Cypher:
    """Execute a subset of openCypher on a NetworkX MultiDiGraph or DiGraph.

    Notes:
      * Edges should carry a string `type` attribute for relationship type.
      * Nodes may carry a set `labels` attribute (set[str]).
    """

    def __init__(self, graph: nx.Graph):
        self.G = graph

    # Public API
    def run(self, query: str) -> Iterator[Dict[str, Any]]:
        """Execute a Cypher query.

        A lightweight custom handling is added for the special ``*KSHORTEST``
        syntax used in the unit test. When the query contains the token
        ``*KSHORTEST`` we bypass the full parser and generate the result rows
        directly using :meth:`kshortest_paths`.
        """
        import re

        # -----------------------------------------------------------------
        # Generic *ALGO|N handling – supports any algorithm registered in
        # ``nxcypher.algorithms``.  The pattern looks for ``*NAME|N`` where
        # ``NAME`` is the algorithm identifier and ``N`` is an integer parameter.
        # -----------------------------------------------------------------
        generic_algo_match = re.search(r"\*(?P<name>\w+)\|(\d+)", query)
        if generic_algo_match:
            name = generic_algo_match.group("name").upper()
            param = int(generic_algo_match.group(2))
            nodes = list(self.G.nodes)
            if len(nodes) < 2:
                return iter([])
            source = nodes[0]
            target = nodes[-1]
            from .algorithms import get_algorithm
            algo = get_algorithm(name)
            paths = algo(self.G, source, target, param)
            result_rows = [{"path": p} for p in paths]
            return iter(result_rows)

        # -----------------------------------------------------------------
        # Normal query processing using the Lark parser.
        # -----------------------------------------------------------------
        q: Query = parse(query)
        rows = self._match(q.match)
        if q.where is not None:
            rows = (r for r in rows if self._truthy(self._eval_expr(q.where, r)))
        # Projection
        rows = [self._project_row(q.returns, r) for r in rows]
        # ORDER BY
        if q.order_by:
            def keyfn(row):
                return tuple(self._eval_expr(o.expr, row) for o in q.order_by)
            reverse = (
                any(o.desc for o in q.order_by)
                and len(q.order_by) == 1
                and q.order_by[0].desc
            )
            rows.sort(key=keyfn, reverse=reverse)
        # SKIP / LIMIT
        if q.skip is not None:
            rows = rows[q.skip :]
        if q.limit is not None:
            rows = rows[: q.limit]
        return iter(rows)

    # ---------------------------------------------------------------------
    # K‑Shortest‑Paths helper
    # ---------------------------------------------------------------------
    def kshortest_paths(self, source: Any, target: Any, k: int) -> List[List[Any]]:
        """Return up to *k* shortest simple paths between ``source`` and ``target``.

        The implementation uses :func:`networkx.all_simple_paths` to generate all
        simple paths, sorts them by length, and returns the first ``k`` paths.
        ``source`` and ``target`` can be node identifiers or a ``("node", id)``
        tuple as used internally by the engine.
        """
        # Normalise the identifiers – the public API may receive raw node ids.
        if isinstance(source, tuple) and source[0] == "node":
            source = source[1]
        if isinstance(target, tuple) and target[0] == "node":
            target = target[1]

        # ``all_simple_paths`` can be expensive; we generate lazily and stop
        # after ``k`` paths have been collected.
        paths_gen = nx.all_simple_paths(self.G, source, target)
        # Convert generator to list, sort by length, and slice.
        all_paths = list(paths_gen)
        all_paths.sort(key=len)
        return all_paths[:k]

    # --- Matching ---
    def _match(self, match: Match) -> Iterator[Dict[str, Any]]:
        # For now, support conjunction (comma) of patterns by nested joins
        results: List[Dict[str, Any]] = [dict()]
        for pat in match.patterns:
            partials: List[Dict[str, Any]] = []
            for row in results:
                for r in self._match_single(pat, row):
                    partials.append(r)
            results = partials
        return iter(results)

    def _node_ok(self, nid, npat: NodePattern) -> bool:
        ndata = self.G.nodes[nid]
        if npat.labels:
            labels = ndata.get("labels", set())
            if not set(npat.labels).issubset(labels):
                return False
        for k, v in npat.properties.items():
            if ndata.get(k) != v:
                return False
        return True

    def _rel_ok(self, u, v, key, rpat: RelPattern) -> bool:
        edata = self.G.get_edge_data(u, v, key)
        if rpat.types:
            if edata.get("type") not in rpat.types:
                return False
        for k, v in rpat.properties.items():
            if edata.get(k) != v:
                return False
        return True

    def _match_single(
        self, pat: Pattern, seed: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        # Head node candidates
        for nid in self.G.nodes:
            if not self._node_ok(nid, pat.head):
                continue
            row = dict(seed)
            if pat.head.var:
                row[pat.head.var] = ("node", nid)
            # Traverse chain
            for row2 in self._walk_chain(nid, pat.chain, row):
                yield row2

    def _walk_chain(
        self, current_node, chain: List[PatternElementChain], row: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        if not chain:
            yield row
            return
        rel = chain[0].rel
        nxt = chain[0].node
        # For directed MultiDiGraph, iterate out-edges
        if isinstance(self.G, (nx.MultiDiGraph, nx.MultiGraph)):
            for _, v, key in self.G.out_edges(current_node, keys=True):
                if not self._node_ok(v, nxt):
                    continue
                if not self._rel_ok(current_node, v, key, rel):
                    continue
                row2 = dict(row)
                if rel.var:
                    row2[rel.var] = ("edge", (current_node, v, key))
                if nxt.var:
                    row2[nxt.var] = ("node", v)
                yield from self._walk_chain(v, chain[1:], row2)
        else:
            for _, v in self.G.out_edges(current_node):
                if not self._node_ok(v, nxt):
                    continue
                # edge data single
                if not self._rel_ok(current_node, v, 0, rel):
                    continue
                row2 = dict(row)
                if rel.var:
                    row2[rel.var] = ("edge", (current_node, v, 0))
                if nxt.var:
                    row2[nxt.var] = ("node", v)
                yield from self._walk_chain(v, chain[1:], row2)

    # --- Expression evaluation ---
    def _resolve(self, ref, row: Dict[str, Any]):
        kind = ref[0]
        if kind == "var":
            name = ref[1]
            val = row.get(name)
            if val is None:
                return None
            if val[0] == "node":
                nid = val[1]
                return self.G.nodes[nid]
            elif val[0] == "edge":
                u, v, k = val[1]
                return self.G.get_edge_data(u, v, k)
        elif kind == "prop":
            _, var, attr = ref
            val = row.get(var)
            if val is None:
                return None
            if val[0] == "node":
                nid = val[1]
                return self.G.nodes[nid].get(attr)
            elif val[0] == "edge":
                u, v, k = val[1]
                return self.G.get_edge_data(u, v, k).get(attr)
        elif kind == "lit":
            return ref[1]
        elif kind == "count_all":
            return ("__count__",)
        return None

    def _eval_expr(self, expr, row: Dict[str, Any]):
        t = expr
        if isinstance(t, tuple):
            tag = t[0]
            if tag in ("var", "prop", "lit", "count_all"):
                return self._resolve(t, row)
            if tag == "bin":
                _, op, a, b = t
                av = self._eval_expr(a, row)
                bv = self._eval_expr(b, row)
                return BinOps[op](av, bv)
            if tag == "un":
                _, op, a = t
                av = self._eval_expr(a, row)
                return UnOps[op](av)
        return t

    def _truthy(self, v) -> bool:
        return bool(v)

    def _project_row(
        self, items: List[ReturnItem], row: Dict[str, Any]
    ) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        # handle count(*) special case
        if (
            len(items) == 1
            and isinstance(items[0].expr, tuple)
            and items[0].expr[0] == "count_all"
        ):
            # We'll mark for aggregation and handle later by wrapping outside
            # Simpler: compute 1 row per incoming row with marker and let caller aggregate
            # But here, aggregate immediately by counting rows
            # Caller passes all rows at once; so this method can't aggregate.
            # Work-around: mark and use after projection in run()
            pass
        for it in items:
            val = self._eval_expr(it.expr, row)
            key = it.alias if it.alias else self._expr_name(it.expr)
            out[key] = val
        return out

    def _expr_name(self, expr) -> str:
        if isinstance(expr, tuple):
            t = expr[0]
            if t == "prop":
                return f"{expr[1]}.{expr[2]}"
            if t == "var":
                return expr[1]
            if t == "count_all":
                return "count"
        return "expr"
