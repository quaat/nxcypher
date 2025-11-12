from __future__ import annotations
from lark import Lark, Transformer, v_args, Token, Tree
from typing import Optional

# Explicit imports of the model classes used by the transformer.
from .model import (
    Query,
    Match,
    Pattern,
    PatternElementChain,
    NodePattern,
    RelPattern,
    ReturnItem,
    OrderItem,
)

with open(__file__.replace("parser.py", "grammar/cypher.lark"), "r") as f:
    _GRAMMAR = f.read()

_lark = Lark(
    _GRAMMAR,
    start="start",
    parser="lalr",
    propagate_positions=True,
    maybe_placeholders=False,
)


def parse(query: str):
    tree = _lark.parse(query)
    return _AstBuilder().transform(tree)


def _as_str(t: Optional[Token]) -> Optional[str]:
    if t is None:
        return None
    return str(t)


@v_args(inline=True)
class _AstBuilder(Transformer):
    def query(self, match, where, returns, order=None, skip=None, limit=None):
        order_items = order or []
        return Query(
            match=match,
            where=where,
            returns=returns,
            order_by=order_items,
            skip=int(skip.value) if skip else None,
            limit=int(limit.value) if limit else None,
        )

    def match_clause(self, *patterns):
        return Match(patterns=list(patterns))

    def pattern(self, head, *chains):
        return Pattern(head=head, chain=list(chains))

    def pattern_element_chain(self, rel, node):
        return PatternElementChain(rel=rel, node=node)

    def node_pattern(self, *parts):
        """Construct a :class:`NodePattern`.

        The grammar may provide the variable name via the ``var`` rule, which the
        transformer currently returns a tuple ``("var", name)``.  The original
        implementation only looked for raw ``Token`` instances, causing the
        variable to be lost (``var`` stayed ``None``).  This broke WHERE clause
        evaluation because the row dictionary never contained the node variable.

        We now recognise the ``("var", name)`` tuple and extract the name.
        """
        var: str | None = None
        labels: tuple = ()
        props: dict = {}
        for p in parts:
            # ``var`` rule is a Tree with data 'var' containing a CNAME token.
            if isinstance(p, Tree) and getattr(p, "data", None) == "var":
                # The first child is the token with the variable name.
                var = str(p.children[0])
            # ``var`` rule could also be a tuple ('var', name) if other transformers emit it.
            elif isinstance(p, tuple) and p and p[0] == "var":
                var = p[1]
            elif isinstance(p, Token):
                # Fallback for any stray token (should not happen with current grammar)
                var = str(p)
            elif isinstance(p, tuple):
                # Labels are emitted as a tuple of label strings
                labels = p
            elif isinstance(p, dict):
                props = p
        return NodePattern(var=var, labels=labels, properties=props)

    def relationship_pattern(self, *parts):
        """Construct a :class:`RelPattern`.

        Mirrors the logic of ``node_pattern`` – the optional variable is emitted
        as a ``('var', name)`` tuple.
        """
        var: str | None = None
        types: tuple = ()
        props: dict = {}
        for p in parts:
            if isinstance(p, Tree) and getattr(p, "data", None) == "var":
                var = str(p.children[0])
            elif isinstance(p, tuple) and p and p[0] == "var":
                var = p[1]
            elif isinstance(p, Token):
                var = str(p)
            elif isinstance(p, tuple):
                types = p
            elif isinstance(p, dict):
                props = p
        return RelPattern(var=var, types=types, properties=props)

    def labels(self, *names):
        return tuple(str(n) for n in names)

    def reltypes(self, name):
        return (str(name),)

    def properties(self, *props):
        out = {}
        for k, v in props:
            out[str(k)] = v
        return out

    def prop(self, k, v):
        return (str(k), v)

    def where_clause(self, expr):
        return expr

    def return_clause(self, *items):
        return list(items)

    def return_item(self, expr, alias=None):
        return ReturnItem(expr=expr, alias=str(alias) if alias else None)

    def order_clause(self, *items):
        return list(items)

    def order_item(self, expr, order=None):
        desc = (str(order).upper() == "DESC") if order else False
        return OrderItem(expr=expr, desc=desc)

    # --- expressions ---
    def var_ref(self, name):
        return ("var", str(name))

    def prop_access(self, var, attr):
        return ("prop", str(var), str(attr))

    def string(self, s):
        return ("lit", s[1:-1])

    def number(self, n):
        return ("lit", float(n))

    def true(self):
        return ("lit", True)

    def false(self):
        return ("lit", False)

    def null(self):
        return ("lit", None)

    def count_all(self):
        return ("count_all",)

    def eq(self):
        return "=="

    def ne(self):
        return "!="

    def lt(self):
        return "<"

    def le(self):
        return "<="

    def gt(self):
        return ">"

    def ge(self):
        return ">="

    def compare_op(self, a, op, b):
        return ("bin", str(op), a, b)

    def add(self, a, b):
        return ("bin", "+", a, b)

    def sub(self, a, b):
        return ("bin", "-", a, b)

    def mul(self, a, b):
        return ("bin", "*", a, b)

    def div(self, a, b):
        return ("bin", "/", a, b)

    def mod(self, a, b):
        return ("bin", "%", a, b)

    def neg(self, a):
        return ("un", "-", a)

    def and_op(self, a, b):
        return ("bin", "AND", a, b)

    def or_op(self, a, b):
        return ("bin", "OR", a, b)

    def not_op(self, a):
        return ("un", "NOT", a)
