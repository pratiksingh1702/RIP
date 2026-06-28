"""Dart / Flutter Repository Intelligence Parser - Pure Python, Zero Dependencies."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from core.parser.base import BaseParser, ParsedEntity, ParsedFile, ParsedRelationship

# ============================================================================
# COMPILED REGEXES
# ============================================================================

_IMPORT_RE = re.compile(r"""^\s*import\s+['"]([^'"]+)['"]\s*(?:as\s+\w+\s*)?(?:show\s+[\w,\s]+)?;""", re.MULTILINE)
_ENUM_RE = re.compile(r"^\s*enum\s+(\w+)", re.MULTILINE)
_MIXIN_RE = re.compile(r"^\s*mixin\s+(\w+)", re.MULTILINE)
_EXTENSION_RE = re.compile(r"^\s*extension\s+(\w+)\s+on\b", re.MULTILINE)

_CLASS_RE = re.compile(
    r"^[ \t]*(?:abstract\s+)?class\s+"
    r"(\w+)"
    r"(?:\s+extends\s+([\w<>?,\s]+?))?"
    r"(?:\s+with\s+([\w<>?,\s]+?))?"
    r"(?:\s+implements\s+([\w<>?,\s]+?))?"
    r"\s*\{",
    re.MULTILINE,
)

_STATE_READ_RE = re.compile(r"\b\w+\s*\.\s*(?:watch|read|listen|select)\s*[\(<]\s*([A-Z][A-Za-z_]\w*)")
_HTTP_CALL_RE = re.compile(r"\b(\w+)\s*\.\s*(get|post|put|patch|delete|head|request|fetch)\s*\(\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_FEATURE_PATH_RE = re.compile(r"[/\\]features[/\\]([^/\\]+)[/\\]")
_MAIN_FUNC_RE = re.compile(r"^\s*(?:void|Future<void>)\s+main\s*\(", re.MULTILINE)

# ============================================================================
# CONSTANTS
# ============================================================================

_WIDGET_BASES: frozenset[str] = frozenset({
    "StatelessWidget", "StatefulWidget", "State", "Widget",
    "ConsumerWidget", "ConsumerStatefulWidget", "HookWidget", "HookConsumerWidget",
    "InheritedWidget", "InheritedNotifier", "InheritedModel",
    "RenderObjectWidget", "LeafRenderObjectWidget",
    "SingleChildRenderObjectWidget", "MultiChildRenderObjectWidget",
    "PreferredSizeWidget", "AnimatedWidget", "ImplicitlyAnimatedWidget",
})

_SUFFIX_TYPE_MAP: list[tuple[str, str]] = [
    ("Repository", "repository"), ("Repo", "repository"),
    ("Service", "service"), ("Provider", "provider"),
    ("Notifier", "provider"), ("Cubit", "provider"), ("Bloc", "provider"),
    ("Controller", "provider"), ("Store", "provider"), ("ViewModel", "provider"),
    ("ApiClient", "api_client"), ("Client", "api_client"),
    ("Datasource", "api_client"), ("DataSource", "api_client"),
    ("RemoteSource", "api_client"), ("LocalSource", "api_client"),
    ("UseCase", "use_case"), ("Interactor", "use_case"),
    ("Screen", "widget"), ("Page", "widget"), ("View", "widget"),
    ("Dialog", "widget"), ("Sheet", "widget"), ("Modal", "widget"), ("Widget", "widget"),
    ("Router", "router"), ("Middleware", "middleware"),
    ("Interceptor", "middleware"), ("Guard", "middleware"),
    ("Config", "config"), ("Configuration", "config"),
    ("Mapper", "mapper"), ("Converter", "mapper"), ("Transformer", "mapper"),
    ("Validator", "validator"),
    ("Model", "model"), ("Entity", "model"), ("Dto", "model"),
    ("Request", "model"), ("Response", "model"),
]

_NOISE_NAMES: frozenset[str] = frozenset({
    "context", "ref", "child", "key", "builder", "router", "themeState",
    "mounted", "widget", "state", "super", "this", "null", "true", "false",
    "_", "it", "e", "err", "error", "value", "result", "data", "response",
    "request", "index", "item", "i", "j", "k", "x", "y", "ok", "success",
    "build", "initState", "dispose", "setState", "fromJson", "toJson",
    "toString", "hashCode", "operator", "copyWith",
})


def _classify(name: str, bases: list[str]) -> str:
    for b in bases:
        if b in _WIDGET_BASES:
            return "widget"
    for suffix, etype in _SUFFIX_TYPE_MAP:
        if name.endswith(suffix):
            return etype
    return "class"


def _strip_generics(s: str) -> str:
    return re.sub(r"<[^>]*(?:<[^>]*>[^>]*)?>", "", s).strip()


def _find_brace_end(content: str, start: int) -> int:
    depth = 0
    for i in range(start, len(content)):
        if content[i] == "{": depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(content) - 1


def _module_fqn(file_path: Path) -> str:
    parts = list(file_path.with_suffix("").parts)
    if "lib" in parts:
        parts = parts[parts.index("lib"):]
    return ".".join(p for p in parts if p not in ("/", "\\"))


# ============================================================================
# MAIN PARSER
# ============================================================================

class DartParser(BaseParser):
    """Pure-Python Dart parser - no tree-sitter dependency."""

    language = "dart"

    def __init__(self) -> None:
        pass

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix == ".dart"

    def parse_file(self, file_path: Path, content: str) -> ParsedFile:
        fp = str(file_path)
        module_fqn = _module_fqn(file_path)
        n_lines = max(content.count('\n') + 1, 1)

        entities: list[ParsedEntity] = []
        relationships: list[ParsedRelationship] = []
        symbol_table: dict[str, str] = {}
        imports: list[str] = []

        # ── Module entity ──────────────────────────────────────────────────
        module = ParsedEntity(
            entity_type="module", name=file_path.stem, fqn=module_fqn,
            file_path=fp, line_start=1, line_end=n_lines, language="dart",
            docstring=None, decorators=[], is_exported=True, raw_code=content,
        )
        entities.append(module)
        symbol_table[file_path.stem] = module_fqn

        # ── Imports ────────────────────────────────────────────────────────
        for m in _IMPORT_RE.finditer(content):
            imp = m.group(1)
            imports.append(imp)
            relationships.append(ParsedRelationship(
                module_fqn, imp, "IMPORTS", fp,
                content[:m.start()].count('\n') + 1
            ))

        # ── Enums ──────────────────────────────────────────────────────────
        for m in _ENUM_RE.finditer(content):
            name = m.group(1)
            if name in _NOISE_NAMES:
                continue
            fqn = f"{module_fqn}.{name}"
            line = content[:m.start()].count('\n') + 1
            try:
                brace = content.index("{", m.end())
                end = _find_brace_end(content, brace)
            except ValueError:
                end = m.end()
            entities.append(ParsedEntity(
                entity_type="enum", name=name, fqn=fqn, file_path=fp,
                line_start=line, line_end=content[:end].count('\n') + 1,
                language="dart", docstring=None, decorators=[],
                is_exported=not name.startswith("_"),
                raw_code=content[m.start():end + 1],
            ))
            symbol_table[name] = fqn

        # ── Mixins ─────────────────────────────────────────────────────────
        for m in _MIXIN_RE.finditer(content):
            name = m.group(1)
            if name in _NOISE_NAMES:
                continue
            fqn = f"{module_fqn}.{name}"
            line = content[:m.start()].count('\n') + 1
            try:
                brace = content.index("{", m.end())
                end = _find_brace_end(content, brace)
            except ValueError:
                end = m.end()
            entities.append(ParsedEntity(
                entity_type="mixin", name=name, fqn=fqn, file_path=fp,
                line_start=line, line_end=content[:end].count('\n') + 1,
                language="dart", docstring=None, decorators=[],
                is_exported=True, raw_code=content[m.start():end + 1],
            ))
            symbol_table[name] = fqn

        # ── Extensions ─────────────────────────────────────────────────────
        for m in _EXTENSION_RE.finditer(content):
            name = m.group(1)
            if name in _NOISE_NAMES:
                continue
            fqn = f"{module_fqn}.{name}"
            line = content[:m.start()].count('\n') + 1
            try:
                brace = content.index("{", m.end())
                end = _find_brace_end(content, brace)
            except ValueError:
                end = m.end()
            entities.append(ParsedEntity(
                entity_type="extension", name=name, fqn=fqn, file_path=fp,
                line_start=line, line_end=content[:end].count('\n') + 1,
                language="dart", docstring=None, decorators=[],
                is_exported=True, raw_code=content[m.start():end + 1],
            ))
            symbol_table[name] = fqn

        # ── Classes ────────────────────────────────────────────────────────
        for cm in _CLASS_RE.finditer(content):
            name = cm.group(1)
            if name in _NOISE_NAMES:
                continue

            ext_raw = cm.group(2) or ""
            mix_raw = cm.group(3) or ""
            impl_raw = cm.group(4) or ""

            ext_name = _strip_generics(ext_raw) if ext_raw else ""
            mixins = [_strip_generics(x).strip() for x in mix_raw.split(",") if x.strip()] if mix_raw else []
            impls = [_strip_generics(x).strip() for x in impl_raw.split(",") if x.strip()] if impl_raw else []
            bases = ([ext_name] if ext_name else []) + mixins

            etype = _classify(name, bases)
            fqn = f"{module_fqn}.{name}"
            line = content[:cm.start()].count('\n') + 1

            try:
                brace = content.index("{", cm.end() - 1)
            except ValueError:
                continue
            end = _find_brace_end(content, brace)

            entities.append(ParsedEntity(
                entity_type=etype, name=name, fqn=fqn, file_path=fp,
                line_start=line, line_end=content[:end].count('\n') + 1,
                language="dart", docstring=None, decorators=[],
                is_exported=not name.startswith("_"),
                raw_code=content[cm.start():end + 1],
            ))
            symbol_table[name] = fqn

            # Inheritance relationships
            if ext_name:
                relationships.append(ParsedRelationship(fqn, ext_name, "EXTENDS", fp, line))
            for iface in impls:
                relationships.append(ParsedRelationship(fqn, iface, "IMPLEMENTS", fp, line))
            for mix in mixins:
                relationships.append(ParsedRelationship(fqn, mix, "MIXES_IN", fp, line))

        # ── State management USES ──────────────────────────────────────────
        for m in _STATE_READ_RE.finditer(content):
            pname = m.group(1)
            if pname and pname not in _NOISE_NAMES:
                line = content[:m.start()].count('\n') + 1
                for e in reversed(entities):
                    if e.line_start <= line <= e.line_end and e.entity_type != "module":
                        pfqn = symbol_table.get(pname, pname)
                        relationships.append(ParsedRelationship(e.fqn, pfqn, "USES", fp, line))
                        break

        # ── Method/Function CALLS ──────────────────────────────────────────
        for m in re.finditer(r'(?:(\w+)\s*\.\s*)?(\w+)\s*\([^)]*\)', content):
            obj = m.group(1)
            method = m.group(2)
            if method and method[0].islower() and method not in _NOISE_NAMES:
                line = content[:m.start()].count('\n') + 1
                callee = f"{obj}.{method}" if obj else method
                # Find enclosing entity
                for e in reversed(entities):
                    if e.line_start <= line <= e.line_end and e.entity_type != "module":
                        relationships.append(ParsedRelationship(e.fqn, callee, "CALLS", fp, line))
                        break
        
        # ── HTTP API calls ─────────────────────────────────────────────────
        for m in _HTTP_CALL_RE.finditer(content):
            verb = m.group(2).upper()
            path = m.group(3)
            line = content[:m.start()].count('\n') + 1
            for e in reversed(entities):
                if e.line_start <= line <= e.line_end and e.entity_type != "module":
                    relationships.append(ParsedRelationship(
                        e.fqn, f"endpoint:{verb}:{path}", "CALLS_ENDPOINT", fp, line
                    ))
                    break

        # ── Feature detection ──────────────────────────────────────────────
        fm = _FEATURE_PATH_RE.search(fp)
        feature = fm.group(1) if fm else None
        is_entry = bool(_MAIN_FUNC_RE.search(content))

        if feature:
            ffqn = f"feature:{feature}"
            for e in entities:
                if e.entity_type in ("widget", "repository", "provider", "service",
                                     "api_client", "use_case", "router"):
                    relationships.append(ParsedRelationship(e.fqn, ffqn, "BELONGS_TO", fp, 0))

        if is_entry:
            for e in entities:
                if e.entity_type == "module":
                    relationships.append(ParsedRelationship(
                        e.fqn, "app:entry_points", "IS_ENTRY_POINT", fp, 0
                    ))

        # ── Deduplicate relationships using from_fqn (not from_entity) ─────
        seen = set()
        deduped = []
        for r in relationships:
            # Use from_fqn and to_fqn - check what ParsedRelationship actually uses
            try:
                k = (r.from_fqn, r.to_fqn, r.relationship_type)
            except AttributeError:
                # Fallback: try from_entity/to_entity
                try:
                    k = (r.from_entity, r.to_entity, r.relationship_type)
                except AttributeError:
                    # Last resort: skip dedup for this relationship
                    deduped.append(r)
                    continue
            if k not in seen:
                seen.add(k)
                deduped.append(r)

        return ParsedFile(
            file_path=fp, language=self.language,
            entities=entities, relationships=deduped,
            imports=imports,
            sha256_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        )