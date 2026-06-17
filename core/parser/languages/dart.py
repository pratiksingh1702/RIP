"""Dart parser (for Flutter and Dart projects)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tree_sitter import Node, Parser
from tree_sitter_language_pack import get_language

from core.parser.base import BaseParser, ParsedEntity, ParsedFile, ParsedRelationship


class DartParser(BaseParser):
    language = "dart"

    def __init__(self) -> None:
        self._lang = get_language("dart")
        self._parser = Parser(self._lang)

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix in (".dart",)

    def parse_file(self, file_path: Path, content: str) -> ParsedFile:
        tree = self._parser.parse(content.encode("utf-8"))
        module = self._module_name(file_path)
        imports = self._extract_imports(tree.root_node)
        entities: list[ParsedEntity] = []
        relationships: list[ParsedRelationship] = []
        known_symbols: dict[str, str] = {}

        lines = content.splitlines()

        # Add module entity
        module_entity = ParsedEntity(
            entity_type="module",
            name=module.split(".")[-1] or file_path.stem,
            fqn=module,
            file_path=str(file_path),
            line_start=1,
            line_end=len(lines),
            language=self.language,
            docstring=None,
            decorators=[],
            is_exported=True,
            raw_code=content,
        )
        entities.append(module_entity)
        known_symbols[module_entity.name] = module_entity.fqn

        # First pass: collect all entities
        self._collect_entities(
            tree.root_node,
            entities,
            relationships,
            known_symbols,
            module,
            file_path,
            content,
        )

        # Second pass: collect imports and calls
        self._collect_relationships(
            tree.root_node,
            relationships,
            known_symbols,
            entities,
            module,
            file_path,
        )

        return ParsedFile(
            file_path=str(file_path),
            language=self.language,
            entities=entities,
            relationships=relationships,
            imports=imports,
            sha256_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def _collect_entities(
        self,
        node: Node,
        entities: list[ParsedEntity],
        relationships: list[ParsedRelationship],
        known_symbols: dict[str, str],
        module: str,
        file_path: Path,
        content: str,
        parent_fqn: str | None = None,
    ) -> None:
        if node.type == "class_definition":
            class_name = self._find_class_name(node)
            if class_name:
                class_entity = self._create_class_entity(
                    node, class_name, module, file_path, content
                )
                entities.append(class_entity)
                known_symbols[class_name] = class_entity.fqn

                # Check for extends
                superclass_name = self._find_superclass_name(node)
                if superclass_name:
                    relationships.append(
                        ParsedRelationship(
                            class_entity.fqn,
                            superclass_name,
                            "EXTENDS",
                            str(file_path),
                            node.start_point[0] + 1,
                        )
                    )

                # Process class body and methods
                class_body = None
                for child in node.children:
                    if child.type == "class_body":
                        class_body = child
                        break
                if class_body:
                    children = list(class_body.children)
                    for index, child in enumerate(children):
                        target_node = child
                        if target_node.type in ("method_signature", "function_signature"):
                            method_name = self._find_function_name(target_node)
                            if method_name:
                                body_node = self._next_function_body(children, index)
                                method_entity = self._create_function_entity(
                                    target_node,
                                    method_name,
                                    class_entity.fqn,
                                    file_path,
                                    content,
                                    body_node=body_node,
                                )
                                entities.append(method_entity)
                                known_symbols[method_name] = method_entity.fqn
                                relationships.append(
                                    ParsedRelationship(
                                        class_entity.fqn,
                                        method_entity.fqn,
                                        "CONTAINS",
                                        str(file_path),
                                        target_node.start_point[0] + 1,
                                    )
                                )
                        # Recurse into class body children with class as parent
                        self._collect_entities(
                            child,
                            entities,
                            relationships,
                            known_symbols,
                            module,
                            file_path,
                            content,
                            class_entity.fqn,
                        )
                return

        elif node.type in ("function_signature", "function_expression") and (
            parent_fqn is None or parent_fqn == module
        ):
            func_name = self._find_function_name(node)
            if func_name and func_name not in known_symbols:
                func_entity = self._create_function_entity(
                    node,
                    func_name,
                    module,
                    file_path,
                    content,
                    body_node=self._next_sibling_function_body(node),
                )
                entities.append(func_entity)
                known_symbols[func_name] = func_entity.fqn

        for child in node.children:
            self._collect_entities(
                child,
                entities,
                relationships,
                known_symbols,
                module,
                file_path,
                content,
                parent_fqn,
            )

    def _collect_relationships(
        self,
        node: Node,
        relationships: list[ParsedRelationship],
        known_symbols: dict[str, str],
        entities: list[ParsedEntity],
        module: str,
        file_path: Path,
    ) -> None:
        if node.type in {"import", "import_or_export", "library_import"}:
            import_path = self._find_import_path(node)
            if import_path:
                relationships.append(
                    ParsedRelationship(
                        module,
                        import_path,
                        "IMPORTS",
                        str(file_path),
                        node.start_point[0] + 1,
                    )
                )
                return
        elif node.type in ("call_expression", "method_invocation", "instance_creation_expression"):
            caller = self._enclosing_fqn(node, entities)
            callee = self._find_call_name(node)
            if caller and callee:
                relationships.append(
                    ParsedRelationship(
                        caller,
                        known_symbols.get(callee, callee),
                        "CALLS",
                        str(file_path),
                        node.start_point[0] + 1,
                    )
                )
        elif node.type == "identifier" and self._is_invocation_identifier(node):
            caller = self._enclosing_fqn(node, entities)
            callee = node.text.decode("utf-8")
            if caller and callee:
                relationships.append(
                    ParsedRelationship(
                        caller,
                        known_symbols.get(callee, callee),
                        "CALLS",
                        str(file_path),
                        node.start_point[0] + 1,
                    )
                )

        for child in node.children:
            self._collect_relationships(
                child,
                relationships,
                known_symbols,
                entities,
                module,
                file_path,
            )

    def _find_class_name(self, node: Node) -> str | None:
        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")
        return None

    def _find_function_name(self, node: Node) -> str | None:
        if node.type == "method_signature":
            for child in node.children:
                if child.type == "function_signature":
                    return self._find_function_name(child)
        # Function signature structure: [return_type, function_name, (args)]
        # Skip any leading type identifiers and find the first identifier after that
        identifiers_found = []
        for child in node.children:
            if child.type in ("identifier", "type_identifier"):
                identifiers_found.append(child)
            elif child.type == "formal_parameter_list":
                # We hit the parameter list - the last identifier before this is the function name
                if identifiers_found:
                    return identifiers_found[-1].text.decode("utf-8")
        # Fallback if we didn't find parameter list
        if len(identifiers_found) >= 2:
            return identifiers_found[-1].text.decode("utf-8")
        elif len(identifiers_found) == 1:
            return identifiers_found[0].text.decode("utf-8")
        return None

    def _find_superclass_name(self, node: Node) -> str | None:
        superclass_node = None
        for child in node.children:
            if child.type == "superclass":
                superclass_node = child
                break
        if superclass_node:
            for child in superclass_node.children:
                if child.type in ("identifier", "type_identifier"):
                    return child.text.decode("utf-8")
        return None

    def _find_import_path(self, node: Node) -> str | None:
        if node.type in ("uri", "configurable_uri", "string_literal"):
            return node.text.decode("utf-8").strip("'\"")
        text = node.text.decode("utf-8")
        if node.type in {"import_or_export", "library_import", "import_specification"}:
            quote = "'" if "'" in text else '"'
            parts = text.split(quote)
            if len(parts) >= 3:
                return parts[1]
        for child in node.children:
            import_path = self._find_import_path(child)
            if import_path:
                return import_path
        return None

    def _create_class_entity(
        self, node: Node, name: str, module: str, file_path: Path, content: str
    ) -> ParsedEntity:
        base_name = self._find_superclass_name(node)
        flutter_bases = {"Widget", "StatelessWidget", "StatefulWidget"}
        entity_type = "widget" if base_name in flutter_bases else "class"
        return ParsedEntity(
            entity_type=entity_type,
            name=name,
            fqn=f"{module}.{name}",
            file_path=str(file_path),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language=self.language,
            docstring=None,
            decorators=[],
            is_exported=not name.startswith("_"),
            raw_code=content[node.start_byte : node.end_byte],
        )

    def _create_function_entity(
        self,
        node: Node,
        name: str,
        parent_fqn: str,
        file_path: Path,
        content: str,
        body_node: Node | None = None,
    ) -> ParsedEntity:
        end_node = body_node or node
        return ParsedEntity(
            entity_type="function",
            name=name,
            fqn=f"{parent_fqn}.{name}",
            file_path=str(file_path),
            line_start=node.start_point[0] + 1,
            line_end=end_node.end_point[0] + 1,
            language=self.language,
            docstring=None,
            decorators=[],
            is_exported=not name.startswith("_"),
            raw_code=content[node.start_byte : end_node.end_byte],
        )

    def _extract_imports(self, node: Node) -> list[str]:
        imports: list[str] = []
        if node.type in {"import", "import_or_export", "library_import"}:
            import_path = self._find_import_path(node)
            if import_path:
                imports.append(import_path)
                return imports
        for child in node.children:
            imports.extend(self._extract_imports(child))
        return imports

    def _find_call_name(self, node: Node) -> str | None:
        for child in node.children:
            if child.type in ("identifier", "type_identifier"):
                return child.text.decode("utf-8")
            if child.type in ("selector", "argument_part"):
                continue
            nested = self._find_call_name(child)
            if nested:
                return nested
        return None

    def _is_invocation_identifier(self, node: Node) -> bool:
        parent = node.parent
        if parent is None:
            return False
        if parent.type in {
            "function_signature",
            "method_signature",
            "class_definition",
            "formal_parameter",
            "formal_parameter_list",
            "type_not_void",
            "type_identifier",
        }:
            return False
        siblings = list(parent.children)
        try:
            index = siblings.index(node)
        except ValueError:
            return False
        return any(sibling.type == "selector" for sibling in siblings[index + 1 :])

    def _enclosing_fqn(self, node: Node, entities: list[ParsedEntity]) -> str | None:
        line = node.start_point[0] + 1
        candidates = [
            entity
            for entity in entities
            if entity.line_start <= line <= entity.line_end
            and entity.entity_type in {"function", "api_route"}
        ]
        if candidates:
            return max(candidates, key=lambda entity: entity.line_start).fqn

        class_candidates = [
            entity
            for entity in entities
            if entity.line_start <= line <= entity.line_end
            and entity.entity_type in {"class", "widget"}
        ]
        if class_candidates:
            return max(class_candidates, key=lambda entity: entity.line_start).fqn
        return None

    def _next_function_body(self, siblings: list[Node], index: int) -> Node | None:
        for sibling in siblings[index + 1 : index + 3]:
            if sibling.type == "function_body":
                return sibling
        return None

    def _next_sibling_function_body(self, node: Node) -> Node | None:
        parent = node.parent
        if parent is None:
            return None
        siblings = list(parent.children)
        try:
            index = siblings.index(node)
        except ValueError:
            return None
        return self._next_function_body(siblings, index)

    def _module_name(self, file_path: Path) -> str:
        parts = list(file_path.with_suffix("").parts)
        if "sample_repos" in parts:
            parts = parts[parts.index("sample_repos") + 2 :]
        elif "lib" in parts:
            parts = parts[parts.index("lib") :]
        return ".".join(part for part in parts if part not in ("index", "main"))
