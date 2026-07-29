"""End-to-end pipeline orchestrator (Phase 10)."""

import re
from typing import Any
from uuid import uuid4
import structlog

from gateway.config import settings
from gateway.core.classifier.engine import ClassifierEngine
from gateway.core.events import PipelineEventSink, get_pipeline_event_bus
from gateway.core.events.bus import get_event_bus
from gateway.core.executor.engine import ExecutorEngine
from gateway.core.memory.conflict_detector import ConflictDetector
from gateway.core.memory.store import SessionStore
from gateway.core.permissions import PermissionEngine, UserRole
from gateway.core.planner.engine import PlannerEngine
from gateway.core.ranker.engine import RankerEngine
from gateway.core.ranker.models import ScoredItem
from gateway.core.router import get_router, get_route_feedback, PathType
from gateway.core.security import get_provenance_tagger, get_injection_scanner
from gateway.core.sources.models import SourceResponse
from gateway.core.sources.registry import get_source_registry
from gateway.core.workspace.goals import get_goal_engine
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.memory import get_workspace_memory
from gateway.server.schemas.common import ContextItem, ContextPackage
from gateway.storage.source_registry import get_gateway_settings

logger = structlog.get_logger(__name__)


class GatewayPipeline:
    """End-to-end pipeline for context gateway."""

    def __init__(self):
        self.classifier = ClassifierEngine()
        self.planner = PlannerEngine()
        self.executor = ExecutorEngine()
        self.ranker = RankerEngine()
        self.permissions = PermissionEngine()
        self.session_store = SessionStore()
        self.conflict_detector = ConflictDetector()
        self.source_registry = get_source_registry()

    async def get_context(
        self,
        task: str,
        max_tokens: int | None = None,
        role: str = "developer",
        trace_session_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
        effort: str = "auto",
        event_sink=None,
    ) -> ContextPackage:
        """Route to fast/medium/deep path based on Router LLM decision."""
        if max_tokens is None:
            editable_settings = await get_gateway_settings()
            max_tokens = int(editable_settings.get("default_max_tokens", 12000))
            role = str(editable_settings.get("default_role", role))

        await self.source_registry.refresh(project_id=project_id, user_id=user_id)

        router = get_router()
        decision = await router.route(task, project_id, user_id, role, effort=effort)
        get_route_feedback().log_route(task, decision, project_id, user_id)

        logger.info(
            "Routing decision: path=%s, confidence=%.2f, escalated=%s",
            decision.path,
            decision.confidence,
            decision.escalated,
        )

        if decision.needs_clarification:
            return ContextPackage(
                session_id="clarify",
                intent="clarification",
                domain="general",
                context=[],
                tokens_used=0,
                tokens_retrieved=0,
                token_allocation={},
                score_summary=[],
                conflicts=[],
                warnings=[],
                needs_clarification=True,
                suggested_interpretations=decision.suggested_interpretations,
            )

        if decision.route_source == "deterministic" and decision.path == PathType.FAST:
            package = await self._execute_fast_path(task, project_id, user_id, decision)
        else:
            package = await self._execute_v7_path(
                task,
                project_id,
                user_id,
                role,
                max_tokens,
                trace_session_id,
                decision,
                event_sink,
            )

        # Record session activity into workspace_memory (skip if recall query)
        if not any(p in task.lower() for p in ["last chat", "memory", "chat history", "previous chat", "who are you"]):
            try:
                from gateway.core.workspace.memory import get_workspace_memory
                ws = project_id or "default"
                await get_workspace_memory().record(
                    workspace_id=ws,
                    project_id=project_id,
                    category="chat",
                    intent=getattr(decision, "intent", "chat_query"),
                    query=task,
                    summary=f"Chat task: {task[:100]}",
                    sources_used=[item.source for item in package.context] if package.context else [],
                    tokens_used=package.tokens_used,
                    created_by=user_id or "user"
                )
            except Exception as exc:
                logger.warning("Pipeline: Failed to auto-record chat memory: %s", exc)

        return package

    async def _execute_fast_path(
        self, task: str, project_id: str | None, user_id: str | None, decision
    ) -> ContextPackage:
        """Fast path: Memory + Knowledge + Goals + Tool Registry. ~100ms."""
        ws = project_id or "default"
        context_items = []

        # Tool discovery check
        selected_tools = getattr(decision, "selected_tools", [])
        if "tools_registry" in selected_tools or any(p in task.lower() for p in ["registered tools", "what tools", "list tools", "available tools", "your tools"]):
            try:
                sources = self.source_registry.list_sources().values()
                source_lines = [f"- **{getattr(s, 'name', 'source')}**: {getattr(s, 'description', 'Registered source')}" for s in sources if getattr(s, 'enabled', True)]
                content = (
                    "### Registered Gateway Tools & Capability Manifest\n\n"
                    "**1. Core Capability Engines:**\n"
                    "- **git_history**: Commits, branches, diffs, author activity\n"
                    "- **agent_runs**: Background agent executions & task logs\n"
                    "- **workspace_memory**: Past chat sessions, active goals, ADRs\n"
                    "- **code_ast**: Tree-sitter AST, call graphs, symbol resolution\n"
                    "- **docker_terminal**: Container sandbox executions & command logs\n\n"
                    "**2. Registered Integration Sources:**\n" +
                    ("\n".join(source_lines) if source_lines else "- No external integrations currently linked.")
                )
                context_items.append(
                    ContextItem(
                        source="source_registry",
                        query_type="list_tools",
                        content=content,
                        metadata={"count": len(sources)},
                        score=1.0,
                    )
                )
            except Exception as exc:
                logger.warning("Failed to fetch registry tools: %s", exc)

        # Self-identity / Agent introduction check
        if "self_identity" in selected_tools or any(p in task.lower() for p in ["who are you", "what is your name", "who made you", "who created you", "tell me about yourself", "what are you"]):
            identity_info = (
                "### Gateway Agent Self-Identity & System Capabilities\n\n"
                "- **System Name**: RIP Context Gateway & AI Assistant\n"
                "- **Primary LLM Engine**: Local Ollama Qwen2.5 (qwen2.5:3b)\n"
                "- **Architecture**: 3-Tier Context Gateway (Fast / Medium / Deep effort routing)\n"
                "- **Core Capabilities**: Multi-Source Context Gathering, AST Code Search, Git Analysis, Goal Tracking, Docker Sandbox Execution"
            )
            context_items.append(
                ContextItem(
                    source="self_identity",
                    query_type="introduction",
                    content=identity_info,
                    metadata={"agent": "RIP Gateway Assistant", "llm": "ollama/qwen2.5:3b"},
                    score=1.0,
                )
            )

        # Conversational greetings & social phrases check
        if "conversational" in selected_tools or re.search(r"\b(hello|hi|hey|how are you|good morning|good evening|good afternoon|thank you|thanks|bye|goodbye|see you)\b", task.lower()):
            t_low = task.lower().strip()
            if any(p in t_low for p in ["thank", "thanks"]):
                reply = "You're welcome! Let me know if you need anything else with your repository or workspace."
            elif any(p in t_low for p in ["bye", "goodbye", "see you"]):
                reply = "Goodbye! Have a great time coding."
            elif "how are you" in t_low:
                reply = "I'm operating at 100% capacity! Ready to help you navigate codebases, search git history, or manage workspace goals."
            else:
                reply = "Hello! I am your RIP Context Gateway Assistant. How can I help you with your codebase today?"

            context_items.append(
                ContextItem(
                    source="conversational",
                    query_type="social_reply",
                    content=f"### Conversational Response\n\n{reply}",
                    metadata={"type": "social_greeting"},
                    score=1.0,
                )
            )

        # Team discovery check
        if any(t in selected_tools for t in ["github", "git_history"]) or any(p in task.lower() for p in ["team", "teammate", "team mate", "who works", "collaborator", "contributor"]):
            try:
                import subprocess
                git_log = subprocess.check_output(
                    ["git", "log", "-n", "30", "--pretty=format:%an <%ae>"],
                    text=True, stderr=subprocess.DEVNULL
                )
                authors = sorted(list(set(line.strip() for line in git_log.splitlines() if line.strip())))
                if authors:
                    authors_formatted = "\n".join(f"- **{a}**" for a in authors)
                    content = f"### Active Repository Team Members & Collaborators\n\n{authors_formatted}"
                    context_items.append(
                        ContextItem(
                            source="git_history",
                            query_type="team_members",
                            content=content,
                            metadata={"count": len(authors)},
                            score=1.0,
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to fetch git team members: %s", exc)

        # Workspace project info check
        if any(p in task.lower() for p in ["project", "which project", "what project", "active project", "current project", "where are we"]):
            import os
            from pathlib import Path
            cwd = os.getcwd()
            proj_name = Path(cwd).name
            project_info = (
                f"### Active Workspace Project Details\n\n"
                f"- **Project Name**: `{proj_name}` (Repository Intelligence Platform)\n"
                f"- **Workspace Path**: `{cwd}`\n"
                f"- **Workspace ID**: `{ws}`\n"
                f"- **Primary Architecture**: Context Gateway, Vector Search, Git AST, Flutter Client"
            )
            context_items.append(
                ContextItem(
                    source="workspace_memory",
                    query_type="project_info",
                    content=project_info,
                    metadata={"workspace": ws, "project_name": proj_name},
                    score=1.0,
                )
            )

        try:
            recent = await get_workspace_memory().get_recent(ws, limit=5)
            if recent:
                content = "### Workspace Recent Activity & Chat Memory\n\n" + "\n".join(
                    f"- **[{r.get('agent_type', 'session')}]** {r.get('task', r.get('summary', 'Chat session'))}" for r in recent
                )
            else:
                content = "### Workspace Recent Activity & Chat Memory\n\n- Active session initialized. No prior chat sessions archived for this workspace project."
            
            context_items.append(
                ContextItem(
                    source="workspace_memory",
                    query_type="recent",
                    content=content,
                    metadata={"workspace": ws, "count": len(recent) if recent else 0},
                    score=1.0,
                )
            )
        except Exception as exc:
            logger.warning("Failed to fetch workspace memory: %s", exc)
            context_items.append(
                ContextItem(
                    source="workspace_memory",
                    query_type="recent",
                    content="### Workspace Memory\n\n- Active session in progress.",
                    metadata={"workspace": ws},
                    score=1.0,
                )
            )

        try:
            knowledge = await get_workspace_knowledge().search(
                ws, task, min_confidence=0.5, limit=3
            )
            if knowledge:
                content = "### Workspace Knowledge & Architectural Decisions\n\n" + "\n".join(
                    f"- **[{k.get('knowledge_type','ADR')}]** {k.get('summary','')}"
                    for k in knowledge
                )
                context_items.append(
                    ContextItem(
                        source="workspace_knowledge",
                        query_type="search",
                        content=content,
                        metadata={"count": len(knowledge)},
                        score=0.9,
                    )
                )
        except Exception as exc:
            logger.warning("Failed to fetch workspace knowledge: %s", exc)

        try:
            goals = await get_goal_engine().get_active(ws, limit=5)
            if goals:
                content = "### Active Workspace Goals & Tasks\n\n" + "\n".join(
                    f"- **{g['name']}** ({g.get('progress',0):.0f}% complete)" for g in goals
                )
                context_items.append(
                    ContextItem(
                        source="workspace_goals",
                        query_type="active",
                        content=content,
                        metadata={"count": len(goals)},
                        score=0.8,
                    )
                )
        except Exception as exc:
            logger.warning("Failed to fetch workspace goals: %s", exc)
        tokens_used = sum(len((c.content or "").split()) for c in context_items)
        pkg = ContextPackage(
            session_id=str(uuid4()),
            intent=decision.reasoning,
            domain="general",
            context=context_items,
            tokens_used=tokens_used,
            tokens_retrieved=tokens_used,
            token_allocation={},
            score_summary=[],
            conflicts=[],
            warnings=[],
            escalated=getattr(decision, "escalated", False),
            route_source=getattr(decision, "route_source", None),
        )
        
        # In V7, deterministic fast paths skip Synthesis LLM
        if getattr(decision, "route_source", "") == "deterministic":
            pkg.llm_synthesized = False
            return pkg
            
        return await self._ensure_human_readable(pkg)

    async def _execute_v7_path(
        self,
        task: str,
        project_id: str | None,
        user_id: str | None,
        role: str,
        max_tokens: int,
        trace_session_id: str | None,
        decision,
        event_sink=None,
    ) -> ContextPackage:
        """Unified V7 execution path based on Planner execution graph."""
        effort_val = getattr(decision, 'effort', 'auto')
        logger.info(f"=== [V7 PATH START] === effort={effort_val}, path={decision.path}, route_source={getattr(decision, 'route_source', 'unknown')}")
        classification = await self.classifier.classify_async(task)
        logger.info(
            "=== [CLASSIFIER RESULT] ===",
            intent=classification.intent.value,
            domain=classification.domain,
            confidence=classification.confidence,
        )
        
        session = await self.session_store.create_session(
            agent_type="mcp_agent", task=task, classification=classification
        )
        session_id = str(session.id)

        async def emit(event):
            if event_sink:
                await event_sink(event)
            if trace_session_id:
                await get_pipeline_event_bus().emit(
                    trace_session_id,
                    stage=str(event["stage"]),
                    status=str(event["status"]),
                    detail=str(event["detail"]),
                    source=event.get("source"),
                    meta=event.get("meta") or {},
                )

        plan = self.planner.plan_execution_graph(
            decision, task, max_tokens, project_id=project_id
        )
        logger.info(
            "=== [PLANNER GRAPH CREATED] ===",
            steps_count=len(plan.steps),
            token_allocation=plan.token_allocation,
        )
        
        execution_result = await self.executor.execute(plan, event_sink=emit)
        successful = [r for r in execution_result.source_responses if r.success]
        logger.info(
            "=== [EXECUTOR COMPLETED] ===",
            total_responses=len(execution_result.source_responses),
            success_count=execution_result.success_count,
            failure_count=execution_result.failure_count,
            total_latency_ms=execution_result.total_latency_ms,
        )

        # Security Gap #2: Wrap and scan tool output
        tagger = get_provenance_tagger()
        scanner = get_injection_scanner()
        raw_items = []
        for r in successful:
            # Wrap output in <tool_output> tags before scanning
            wrapped_content = f'<tool_output source="{r.source}" tool_id="{r.query_type}">\n{r.content}\n</tool_output>'
            raw_items.append({
                "source": r.source,
                "query_type": r.query_type,
                "content": wrapped_content,
                "metadata": r.metadata,
            })
            
        tagged_raw = tagger.tag_all(raw_items)
        clean_items, flagged_items = scanner.scan_all(tagged_raw)
        logger.info(
            "=== [SECURITY SCANNER] ===",
            scanned_count=len(tagged_raw),
            clean_count=len(clean_items),
            flagged_count=len(flagged_items),
        )

        for i, item in enumerate(clean_items):
            if i < len(successful):
                successful[i].content = item.get("content", successful[i].content)

        files_accessed = self._extract_files_from_responses(execution_result.source_responses)
        await self.session_store.update_files_accessed(session.id, files_accessed)

        conflicts = await self.conflict_detector.detect(session.id, files_accessed)

        ranked = await self.ranker.rank_and_compress(
            execution_result.source_responses, classification, task, max_tokens
        )
        
        user_role = self._coerce_role(role)
        filtered = await self.permissions.filter_context(
            ranked.included, user_role, classification.domain, session_id=session_id
        )
        logger.info(
            "=== [RANKING & PERMISSIONS] ===",
            ranked_count=len(ranked.included),
            filtered_count=len(filtered),
            tokens_used=ranked.tokens_used,
        )

        context_items = [
            ContextItem(
                source=item.source,
                query_type=item.query_type,
                content=item.content,
                metadata=item.metadata,
                score=item.score,
            )
            for item in filtered
        ]
        
        warnings = self._build_warnings(execution_result.source_responses)
        tokens_retrieved = sum(r.token_count for r in execution_result.source_responses)
        
        pkg = ContextPackage(
            session_id=session_id,
            intent=classification.intent.value,
            domain=classification.domain,
            context=context_items,
            tokens_used=ranked.tokens_used,
            tokens_retrieved=tokens_retrieved,
            token_allocation=plan.token_allocation,
            score_summary=self._score_summary(ranked.included),
            conflicts=[c.model_dump(mode="json") for c in conflicts] if conflicts else [],
            warnings=warnings,
            escalated=getattr(decision, "escalated", False),
            route_source=getattr(decision, "route_source", None),
        )

        # Conditional Synthesis: Skip LLM format for single tools in FAST effort
        if getattr(decision, "effort", "auto") == "fast" and len(successful) == 1:
            logger.info("=== [SYNTHESIS SKIPPED] === Fast effort single tool path.")
            pkg.llm_synthesized = False
            return pkg
        
        logger.info("=== [SYNTHESIS INVOKED] === Running synthesis LLM to structure response.")
        return await self._ensure_human_readable(pkg)

    def _coerce_role(self, role: str) -> UserRole:
        """Use configured default role if the caller sends an unknown value."""
        try:
            return UserRole(role)
        except ValueError:
            logger.warning("Unknown role supplied, using default", role=role)
            return UserRole(settings.default_role)

    def _extract_files_from_responses(
        self, responses: list[SourceResponse]
    ) -> list[str]:
        """Extract file paths from source metadata and text content."""
        files: set[str] = set()
        for response in responses:
            metadata_files = response.metadata.get("files", [])
            if isinstance(metadata_files, list):
                files.update(str(path) for path in metadata_files if path)
            elif isinstance(metadata_files, str):
                files.add(metadata_files)

            affected = response.metadata.get("affected_files", [])
            if isinstance(affected, list):
                files.update(str(path) for path in affected if path)

            files.update(self._extract_file_paths(response.content))
        return sorted(self._normalize_file_path(path) for path in files if path)

    def _extract_file_paths(self, content: str) -> set[str]:
        patterns = [
            r"[\w./\\-]+\.(?:py|ts|tsx|js|jsx|dart|java|go|rs|md|toml|yaml|yml|json)",
            r"[A-Za-z]:\\[^\s:]+?\.(?:py|ts|tsx|js|jsx|dart|java|go|rs|md|toml|yaml|yml|json)",
        ]
        files: set[str] = set()
        for pattern in patterns:
            for match in re.findall(pattern, content):
                files.add(match.strip("`'\".,;)"))
        return files

    def _normalize_file_path(self, path: str) -> str:
        return path.replace("\\", "/").strip()

    def _build_warnings(self, responses: list[SourceResponse]) -> list[str]:
        warnings = []
        for response in responses:
            if not response.success:
                reason = response.error or "source query failed"
                warnings.append(f"{response.source}/{response.query_type}: {reason}")
        return warnings

    def _score_summary(self, items) -> list[dict[str, Any]]:
        return [
            {
                "source": item.source,
                "query_type": item.query_type,
                "score": item.score,
                "metadata": item.metadata,
            }
            for item in items[:5]
        ]

    def _conflict_detail(self, conflicts) -> str:
        first = conflicts[0]
        files = getattr(first, "overlapping_files", None) or []
        if files:
            return f"{files[0]} is being edited in another active session"
        return "A file conflict was found with another active session"

    async def _ensure_human_readable(self, package: ContextPackage) -> ContextPackage:
        """Ensure all context texts in response package are human readable.
        If non-human-readable content is detected, reformat/rewrite it using the currently configured LLM.
        Track whether LLM synthesis was successfully applied.
        """
        if not package or not package.context:
            return package

        llm_used = False
        was_non_readable = False

        for item in package.context:
            if item.content and not self._is_human_readable(item.content):
                was_non_readable = True
                logger.info(
                    "Non-human-readable content detected in response context; converting using configured LLM",
                    source=item.source,
                )
                converted_text, success = await self._make_human_readable_with_llm(item.content)
                item.content = converted_text
                if success:
                    llm_used = True

        if was_non_readable and not llm_used:
            package.llm_synthesized = False
        else:
            package.llm_synthesized = True

        return package

    def _is_human_readable(self, text: str) -> bool:
        """Check if content string is human readable."""
        if not text or not text.strip():
            return True

        # Check null bytes or control character ratio
        control_chars = sum(
            1 for c in text if not c.isprintable() and c not in "\n\r\t"
        )
        if control_chars / len(text) > 0.03:
            return False

        # Check unicode replacement characters (corrupted encoding)
        if text.count("\ufffd") > 2:
            return False

        # Check raw hex/binary escape sequences like \x80\x91...
        hex_escapes = len(re.findall(r"\\x[0-9a-fA-F]{2}", text))
        if hex_escapes > 3:
            return False

        # Check for exceptionally long continuous non-space tokens (e.g. raw base64 / binary dumps)
        words = text.split()
        if words and len(text) > 100:
            max_word_len = max(len(w) for w in words)
            if max_word_len > 150:
                return False

        return True

    async def _make_human_readable_with_llm(self, text: str) -> tuple[str, bool]:
        """Use currently configured LLM to convert non-human-readable text into clean human-readable text.
        Returns (formatted_text, is_llm_success).
        """
        prompt = (
            "The following text or data in context response is not easily human readable "
            "(it may contain raw binary dumps, corrupted characters, escaped sequences, or unformatted data).\n"
            "Please convert and reformat it into clean, readable, clear human text. "
            "Preserve all relevant technical facts and structure.\n\n"
            f"Raw Content:\n{text[:4000]}"
        )
        try:
            from gateway.core.llm_pool.router import get_llm_router

            llm_router = get_llm_router()
            config = await llm_router.get_config()
            formatted = await llm_router.query_llm(
                prompt=prompt,
                config=config,
                system_prompt="You are an expert assistant that converts raw, corrupted, binary, or obscure text into clean, readable human text.",
                max_tokens=1500,
                temperature=0.1,
            )
            if formatted and formatted.strip():
                return formatted.strip(), True
        except Exception as exc:
            logger.warning("Failed to process text using configured LLM: %s", exc)

        # Fallback cleanup if LLM is unavailable
        cleaned = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
        cleaned = re.sub(r"\\x[0-9a-fA-F]{2}", "", cleaned)
        return cleaned.strip(), False


# Global pipeline instance
_pipeline: GatewayPipeline | None = None


def get_context_pipeline() -> GatewayPipeline:
    """Get the global context pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = GatewayPipeline()
    return _pipeline