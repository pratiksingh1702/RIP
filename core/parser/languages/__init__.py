"""Language-specific parsers."""

__all__ = [
    "PythonParser",
    "JavaParser",
    "GoParser",
    "RustParser",
    "TypeScriptParser",
    "DartParser",
]


def __getattr__(name):
    if name == "PythonParser":
        from core.parser.languages.python import PythonParser
        return PythonParser
    if name == "JavaParser":
        from core.parser.languages.java import JavaParser
        return JavaParser
    if name == "GoParser":
        from core.parser.languages.go import GoParser
        return GoParser
    if name == "RustParser":
        from core.parser.languages.rust import RustParser
        return RustParser
    if name == "TypeScriptParser":
        from core.parser.languages.typescript import TypeScriptParser
        return TypeScriptParser
    if name == "DartParser":
        from core.parser.languages.dart import DartParser
        return DartParser
    raise AttributeError(f"module {__name__} has no attribute {name}")
