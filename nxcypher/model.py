from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Property:
    key: str
    value: Any


@dataclass
class NodePattern:
    var: Optional[str]
    labels: Tuple[str, ...]
    properties: Dict[str, Any]


@dataclass
class RelPattern:
    var: Optional[str]
    types: Tuple[str, ...]
    properties: Dict[str, Any]


@dataclass
class PatternElementChain:
    rel: RelPattern
    node: NodePattern


@dataclass
class Pattern:
    head: NodePattern
    chain: List[PatternElementChain]


@dataclass
class Match:
    patterns: List[Pattern]


@dataclass
class ReturnItem:
    expr: Any
    alias: Optional[str]


@dataclass
class OrderItem:
    expr: Any
    desc: bool = False


@dataclass
class Query:
    match: Match
    where: Optional[Any]
    returns: List[ReturnItem]
    order_by: List[OrderItem] = field(default_factory=list)
    skip: Optional[int] = None
    limit: Optional[int] = None
