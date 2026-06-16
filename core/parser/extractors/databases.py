"""Database model extraction helpers."""

from __future__ import annotations

import ast


def base_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = base_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    if isinstance(node, ast.Subscript):
        return base_name(node.value)
    return ""


def is_sqlalchemy_model(node: ast.ClassDef) -> bool:
    if any(base_name(base).endswith(("Base", "DeclarativeBase")) for base in node.bases):
        return True
    return any(
        isinstance(stmt, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__tablename__"
            for target in stmt.targets
        )
        for stmt in node.body
    )
