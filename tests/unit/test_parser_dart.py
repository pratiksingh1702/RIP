"""Dart parser tests."""

from __future__ import annotations

from pathlib import Path

from core.parser.languages.dart import DartParser


def test_dart_parser_extracts_widgets_functions_imports_and_calls() -> None:
    content = """
import 'package:flutter/material.dart';
import 'src/service.dart';

void topLevelHelper() {
  print('hello');
}

class HomePage extends StatelessWidget {
  Widget build(BuildContext context) {
    return Text(makeTitle());
  }

  String makeTitle() {
    topLevelHelper();
    return 'Home';
  }
}
"""
    result = DartParser().parse_file(Path("lib/main.dart"), content)

    entities = {(entity.entity_type, entity.name) for entity in result.entities}
    relationships = {
        (rel.relationship_type, rel.from_fqn, rel.to_fqn)
        for rel in result.relationships
    }

    assert ("widget", "HomePage") in entities
    assert ("function", "topLevelHelper") in entities
    assert ("function", "build") in entities
    assert "package:flutter/material.dart" in result.imports
    assert "src/service.dart" in result.imports
    assert any(rel[0] == "EXTENDS" and rel[2] == "StatelessWidget" for rel in relationships)
    assert any(rel[0] == "CONTAINS" and rel[2].endswith(".build") for rel in relationships)
    assert any(rel[0] == "IMPORTS" for rel in relationships)
    assert any(rel[0] == "CALLS" and rel[2].endswith("makeTitle") for rel in relationships)
    assert any(rel[0] == "CALLS" and rel[2].endswith("topLevelHelper") for rel in relationships)
