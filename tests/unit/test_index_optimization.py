from pathlib import Path

import pytest

from core.indexer.pipeline import parse_files_parallel
from core.parser.languages.python import PythonParser
from core.parser.registry import LanguageParserRegistry
from core.parser.traversal import FileTraversal

FIXTURE = Path("tests/fixtures/sample_repos/python_simple")


@pytest.mark.asyncio
async def test_parallel_parsing_matches_serial_entity_names() -> None:
    files = [
        FIXTURE / "app.py",
        FIXTURE / "services/user_service.py",
        FIXTURE / "repositories/user_repository.py",
    ]
    parallel_parsed, warnings = await parse_files_parallel(files, max_workers=2)

    parser = PythonParser()
    serial_parsed = [
        parser.parse_file(file_path, file_path.read_text(encoding="utf-8"))
        for file_path in files
    ]

    assert warnings == []
    # Sort by file path to handle any order from parallel execution
    sorted_parallel = sorted(parallel_parsed, key=lambda p: p.file_path)
    sorted_serial = sorted(serial_parsed, key=lambda p: p.file_path)
    assert [
        [entity.name for entity in parsed_file.entities] for parsed_file in sorted_parallel
    ] == [[entity.name for entity in parsed_file.entities] for parsed_file in sorted_serial]


def test_traversal_find_files_alias_matches_iter_source_files() -> None:
    registry = LanguageParserRegistry()
    registry.register(PythonParser())
    traversal = FileTraversal(registry)

    assert traversal.find_files(FIXTURE) == traversal.iter_source_files(FIXTURE)
