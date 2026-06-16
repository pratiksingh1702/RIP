"""Parser registry."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from core.parser.base import BaseParser

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LanguageParserRegistry:
    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> None:
        self._parsers.append(parser)

    def get_parser(self, file_path: Path) -> BaseParser | None:
        for parser in self._parsers:
            if parser.can_parse(file_path):
                return parser
        return None


def build_default_registry(include_experimental: bool = True) -> LanguageParserRegistry:
    """Build the default parser registry, skipping unavailable optional parsers."""
    registry = LanguageParserRegistry()

    # Python parser is always available
    try:
        from core.parser.languages import PythonParser
        registry.register(PythonParser())
    except Exception as exc:
        logger.error("Failed to register Python parser (critical): %s", exc)

    if not include_experimental:
        return registry

    # All other parsers are optional
    optional_parser_classes = []

    # Try to add DartParser
    try:
        from core.parser.languages import DartParser
        optional_parser_classes.append(DartParser)
    except Exception as exc:
        logger.warning("Skipping unavailable parser DartParser: %s", exc)

    # Try to add TypeScriptParser
    try:
        from core.parser.languages import TypeScriptParser
        optional_parser_classes.append(TypeScriptParser)
    except Exception as exc:
        logger.warning("Skipping unavailable parser TypeScriptParser: %s", exc)

    # Try to add JavaParser, GoParser, RustParser
    for lang_name in ("JavaParser", "GoParser", "RustParser"):
        try:
            import core.parser.languages
            parser_cls = getattr(core.parser.languages, lang_name)
            optional_parser_classes.append(parser_cls)
        except Exception as exc:
            logger.warning("Skipping unavailable parser %s: %s", lang_name, exc)

    # Register optional parsers, handling initialization failures
    for parser_cls in optional_parser_classes:
        try:
            registry.register(parser_cls())
        except Exception as exc:
            logger.warning("Skipping unavailable parser %s: %s", parser_cls.__name__, exc)

    return registry
