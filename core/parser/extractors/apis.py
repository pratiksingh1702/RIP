"""API route extraction helpers."""

from __future__ import annotations

import ast

ROUTE_DECORATOR_MARKERS = (
    ".route",
    ".get",
    ".post",
    ".put",
    ".patch",
    ".delete",
    ".head",
    ".options",
)


def decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = decorator_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def is_route_decorator(node: ast.AST) -> bool:
    name = decorator_name(node)
    return any(name.endswith(marker) for marker in ROUTE_DECORATOR_MARKERS)
