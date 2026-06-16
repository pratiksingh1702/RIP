"""Python parser."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from core.parser.base import BaseParser, ParsedEntity, ParsedFile, ParsedRelationship
from core.parser.extractors.apis import decorator_name, is_route_decorator
from core.parser.extractors.databases import is_sqlalchemy_model
from core.parser.extractors.entities import node_source
from core.parser.extractors.imports import extract_imports

FUNCTION_NODES = ast.FunctionDef | ast.AsyncFunctionDef


class PythonParser(BaseParser):
    language = "python"

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix == ".py"

    def parse_file(self, file_path: Path, content: str) -> ParsedFile:
        tree = ast.parse(content, filename=str(file_path))
        lines = content.splitlines()
        module = self._module_name(file_path)
        imports = extract_imports(tree)
        entities: list[ParsedEntity] = []
        relationships: list[ParsedRelationship] = []
        known_symbols: dict[str, str] = {}

        # Add module entity
        module_entity = ParsedEntity(
            entity_type="module",
            name=module.split(".")[-1] or file_path.stem,
            fqn=module,
            file_path=str(file_path),
            line_start=1,
            line_end=len(lines),
            language=self.language,
            docstring=ast.get_docstring(tree),
            decorators=[],
            is_exported=True,
            raw_code=content,
        )
        entities.append(module_entity)
        known_symbols[module_entity.name] = module_entity.fqn

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_entity = self._class_entity(node, file_path, lines, module)
                entities.append(class_entity)
                known_symbols[node.name] = class_entity.fqn
                for base_name in self._class_base_names(node):
                    relationships.append(
                        ParsedRelationship(
                            class_entity.fqn,
                            known_symbols.get(base_name, base_name),
                            "EXTENDS",
                            str(file_path),
                            node.lineno,
                        )
                    )

                methods = [stmt for stmt in node.body if isinstance(stmt, FUNCTION_NODES)]
                for method in methods:
                    method_entity = self._function_entity(
                        method,
                        file_path,
                        lines,
                        f"{module}.{node.name}",
                    )
                    entities.append(method_entity)
                    known_symbols[method.name] = method_entity.fqn
                    relationships.append(
                        ParsedRelationship(
                            class_entity.fqn,
                            method_entity.fqn,
                            "CONTAINS",
                            str(file_path),
                            method.lineno,
                        )
                    )

            elif isinstance(node, FUNCTION_NODES):
                function_entity = self._function_entity(node, file_path, lines, module)
                entities.append(function_entity)
                known_symbols[node.name] = function_entity.fqn

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                source = self._enclosing_fqn(node, entities)
                for alias in node.names:
                    relationships.append(
                        ParsedRelationship(
                            source,
                            alias.name,
                            "IMPORTS",
                            str(file_path),
                            node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                source = self._enclosing_fqn(node, entities)
                module_name = "." * node.level + (node.module or "")
                relationships.append(
                    ParsedRelationship(
                        source,
                        module_name,
                        "IMPORTS",
                        str(file_path),
                        node.lineno,
                    )
                )
            elif isinstance(node, ast.Call):
                caller = self._enclosing_fqn(node, entities)
                callee = self._call_name(node.func)
                if callee:
                    relationships.append(
                        ParsedRelationship(
                            caller,
                            known_symbols.get(callee, callee),
                            "CALLS",
                            str(file_path),
                            getattr(node, "lineno", 1),
                        )
                    )

        return ParsedFile(
            file_path=str(file_path),
            language=self.language,
            entities=entities,
            relationships=relationships,
            imports=imports,
            sha256_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def _class_entity(
        self, node: ast.ClassDef, file_path: Path, lines: list[str], module: str
    ) -> ParsedEntity:
        entity_type = "db_model" if is_sqlalchemy_model(node) else "class"
        return ParsedEntity(
            entity_type=entity_type,
            name=node.name,
            fqn=f"{module}.{node.name}",
            file_path=str(file_path),
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language=self.language,
            docstring=ast.get_docstring(node),
            decorators=[decorator_name(decorator) for decorator in node.decorator_list],
            is_exported=not node.name.startswith("_"),
            raw_code=node_source(lines, node),
        )

    def _function_entity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: Path,
        lines: list[str],
        parent_fqn: str,
    ) -> ParsedEntity:
        decorators = [decorator_name(decorator) for decorator in node.decorator_list]
        has_route = any(is_route_decorator(decorator) for decorator in node.decorator_list)
        return ParsedEntity(
            entity_type="api_route" if has_route else "function",
            name=node.name,
            fqn=f"{parent_fqn}.{node.name}",
            file_path=str(file_path),
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language=self.language,
            docstring=ast.get_docstring(node),
            decorators=decorators,
            is_exported=not node.name.startswith("_"),
            raw_code=node_source(lines, node),
        )

    def _module_name(self, file_path: Path) -> str:
        parts = list(file_path.with_suffix("").parts)
        if "sample_repos" in parts:
            parts = parts[parts.index("sample_repos") + 2 :]
        return ".".join(part for part in parts if part != "__init__")

    def _call_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""

    def _class_base_names(self, node: ast.ClassDef) -> list[str]:
        bases = []
        for base in node.bases:
            name = self._call_name(base)
            if name:
                bases.append(name)
        return bases

    def _enclosing_fqn(self, node: ast.AST, entities: list[ParsedEntity]) -> str:
        line = getattr(node, "lineno", 1)
        candidates = [
            entity
            for entity in entities
            if entity.line_start <= line <= entity.line_end and entity.entity_type != "class"
        ]
        if candidates:
            return max(candidates, key=lambda entity: entity.line_start).fqn

        file_entities = [
            entity for entity in entities if entity.file_path and entity.line_start <= line
        ]
        if file_entities:
            return min(file_entities, key=lambda entity: abs(entity.line_start - line)).fqn
        return "<module>"
