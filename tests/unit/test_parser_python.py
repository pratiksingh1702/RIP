from pathlib import Path

import pytest

from core.parser.languages.python import PythonParser
from core.parser.registry import LanguageParserRegistry
from core.parser.traversal import FileTraversal

FIXTURE = Path("tests/fixtures/sample_repos/python_simple")


def parse_fixture_file(relative: str):
    path = FIXTURE / relative
    return PythonParser().parse_file(path, path.read_text(encoding="utf-8"))


def test_python_parser_extracts_functions_classes_routes_and_models() -> None:
    app = parse_fixture_file("app.py")
    service = parse_fixture_file("services/user_service.py")
    model = parse_fixture_file("models/user.py")

    entities = [*app.entities, *service.entities, *model.entities]
    names = {entity.name for entity in entities}

    assert {"get_user", "UserService", "unused_helper", "User"}.issubset(names)
    assert any(
        entity.name == "get_user" and entity.entity_type == "api_route" for entity in entities
    )
    assert any(entity.name == "User" and entity.entity_type == "db_model" for entity in entities)
    assert all(entity.fqn for entity in entities)


def test_python_parser_extracts_imports_relationships_and_hash() -> None:
    parsed = parse_fixture_file("services/user_service.py")

    assert "repositories.user_repository" in parsed.imports
    assert parsed.sha256_hash
    assert any(rel.relationship_type == "IMPORTS" for rel in parsed.relationships)
    assert any(
        rel.relationship_type == "CALLS" and "find_user" in rel.to_fqn
        for rel in parsed.relationships
    )


def test_file_traversal_skips_syntax_errors_without_crashing() -> None:
    registry = LanguageParserRegistry()
    registry.register(PythonParser())

    parsed_files = FileTraversal(registry).parse_repository(FIXTURE)

    parsed_paths = {Path(parsed.file_path).name for parsed in parsed_files}
    assert "broken.py" not in parsed_paths
    assert "app.py" in parsed_paths


def test_python_parser_raises_syntax_error_for_invalid_direct_parse() -> None:
    with pytest.raises(SyntaxError):
        parse_fixture_file("broken.py")
