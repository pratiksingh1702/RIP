"""Go parser."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tree_sitter import Parser
from tree_sitter_language_pack import get_language

from core.parser.base import BaseParser, ParsedEntity, ParsedFile, ParsedRelationship


class GoParser(BaseParser):
    language = "go"

    def __init__(self) -> None:
        self._lang = get_language("go")
        self._parser = Parser(self._lang)

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix == ".go"

    def parse_file(self, file_path: Path, content: str) -> ParsedFile:
        tree = self._parser.parse(content.encode("utf-8"))
        lines = content.splitlines()
        module = self._module_name(file_path)
        imports = self._extract_imports(tree.root_node, content)
        entities: list[ParsedEntity] = []
        relationships: list[ParsedRelationship] = []

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

        self._walk_tree(tree.root_node, entities, relationships, module, file_path, lines, content)

        return ParsedFile(
            file_path=str(file_path),
            language=self.language,
            entities=entities,
            relationships=relationships,
            imports=imports,
            sha256_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )

    def _walk_tree(
        self,
        node,
        entities: list[ParsedEntity],
        relationships: list[ParsedRelationship],
        module: str,
        file_path: Path,
        lines: list[str],
        content: str,
        parent_fqn: str | None = None,
    ) -> None:
        if node.type == "type_declaration":
            for child in node.named_children:
                if child.type == "type_spec":
                    type_node = child.child_by_field_name("type")
                    if type_node and type_node.type == "struct_type":
                        name_node = child.child_by_field_name("name")
                        name = name_node.text.decode("utf-8") if name_node else "anonymous"
                        entities.append(
                            ParsedEntity(
                                entity_type="class",
                                name=name,
                                fqn=f"{module}.{name}",
                                file_path=str(file_path),
                                line_start=node.start_point[0] + 1,
                                line_end=node.end_point[0] + 1,
                                language=self.language,
                                docstring=None,
                                decorators=[],
                                is_exported=name[0].isupper(),
                                raw_code=content[node.start_byte : node.end_byte],
                            )
                        )
        elif node.type == "function_declaration":
            func_entity = self._function_entity(node, module, file_path, lines, content)
            entities.append(func_entity)

        for child in node.named_children:
            self._walk_tree(
                child, entities, relationships, module, file_path, lines, content, parent_fqn
            )

    def _function_entity(
        self, node, parent_fqn: str, file_path: Path, lines: list[str], content: str
    ) -> ParsedEntity:
        name_node = node.child_by_field_name("name")
        name = name_node.text.decode("utf-8") if name_node else "anonymous"
        return ParsedEntity(
            entity_type="function",
            name=name,
            fqn=f"{parent_fqn}.{name}",
            file_path=str(file_path),
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language=self.language,
            docstring=None,
            decorators=[],
            is_exported=name[0].isupper(),
            raw_code=content[node.start_byte : node.end_byte],
        )

    def _extract_imports(self, node, content: str) -> list[str]:
        imports: list[str] = []
        if node.type == "import_spec":
            path_node = node.child_by_field_name("path")
            if path_node:
                imports.append(path_node.text.decode("utf-8").strip('"'))
        for child in node.named_children:
            imports.extend(self._extract_imports(child, content))
        return imports

    def _module_name(self, file_path: Path) -> str:
        parts = list(file_path.with_suffix("").parts)
        if "sample_repos" in parts:
            parts = parts[parts.index("sample_repos") + 2 :]
        return ".".join(part for part in parts if part not in ("index", "main"))
