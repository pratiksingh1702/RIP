"""Router LLM — Fast, local LLM for intelligent query routing."""
from __future__ import annotations
import asyncio
import json
import logging
import re
from gateway.core.router.models import PathType, RouteDecision, CONFIDENCE_THRESHOLDS
from gateway.core.router.context import get_routing_context
from gateway.core.router.cache import get_route_cache, RouteCacheKey
from gateway.core.router.capability_map import get_capability_map, EffortTier
from gateway.core.permissions.engine import PermissionEngine
from gateway.core.permissions.models import UserRole
from gateway.config import settings

logger = logging.getLogger(__name__)

class RouterLLM:
    """Routes queries to fast/medium/deep using a local LLM with 2s timeout."""

    def __init__(self):
        self.model = getattr(settings, 'router_model', None) or "ollama-local"
        self.timeout = getattr(settings, 'router_timeout', 15.0)
        self.fallback_threshold = getattr(settings, 'router_fallback_threshold', 0.70)
        self._context = get_routing_context()
        self._cache = get_route_cache()
        self.permissions = PermissionEngine()

    async def _stage_0_fast_match(self, query: str) -> RouteDecision | None:
        """Stage 0: Deterministic Fast-Match for known intents."""
        q = query.lower()
        if any(p in q for p in ["registered tools", "what tools", "list tools", "available tools", "show capabilities", "your tools"]):
            return RouteDecision(
                path=PathType.FAST,
                confidence=1.0,
                reasoning="Tool discovery query detected",
                suggested_sources=["workspace_knowledge", "source_registry"],
                selected_tools=["tools_registry"],
                needs_llm=False,
                urgency="low",
                route_source="deterministic"
            )
        if any(p in q for p in ["team", "teammate", "team mate", "who works", "collaborator", "contributor"]):
            return RouteDecision(
                path=PathType.FAST,
                confidence=1.0,
                reasoning="Team / collaborator query detected",
                suggested_sources=["github", "git_history", "workspace_memory"],
                selected_tools=["github", "git_history", "workspace_memory"],
                needs_llm=False,
                urgency="low",
                route_source="deterministic"
            )
        if any(p in q for p in ["last chat", "memory", "chat history", "previous chat", "past memory", "chat and memory", "last message", "chat recall"]):
            return RouteDecision(
                path=PathType.FAST,
                confidence=1.0,
                reasoning="Workspace memory and chat recall query detected",
                suggested_sources=["workspace_memory", "workspace_knowledge", "git_history"],
                selected_tools=["workspace_memory", "workspace_knowledge"],
                needs_llm=False,
                urgency="low",
                route_source="deterministic"
            )
        if any(p in q for p in ["project", "which project", "what project", "active project", "current project", "where are we", "workspace name"]):
            return RouteDecision(
                path=PathType.FAST,
                confidence=1.0,
                reasoning="Active workspace project info query detected",
                suggested_sources=["workspace_memory", "workspace_knowledge"],
                selected_tools=["workspace_memory"],
                needs_llm=False,
                urgency="low",
                route_source="deterministic"
            )
        if any(p in q for p in ["who are you", "what is your name", "who made you", "who created you", "tell me about yourself", "what are you", "identify yourself"]):
            return RouteDecision(
                path=PathType.FAST,
                confidence=1.0,
                reasoning="Self-identity and agent introduction query detected",
                suggested_sources=["self_identity"],
                selected_tools=["self_identity"],
                needs_llm=False,
                urgency="low",
                route_source="deterministic"
            )
        import re
        if re.search(r"\b(hello|hi|hey|how are you|good morning|good evening|good afternoon|thank you|thanks|bye|goodbye|see you)\b", q):
            return RouteDecision(
                path=PathType.FAST,
                confidence=1.0,
                reasoning="Conversational greeting / social phrase detected",
                suggested_sources=["conversational"],
                selected_tools=["conversational"],
                needs_llm=False,
                urgency="low",
                route_source="deterministic"
            )
        return None

    async def _effort_gate(self, effort: str, role: UserRole) -> list[str]:
        """Filter the capability map by effort tier and user permissions."""
        cap_map = get_capability_map()
        
        # Effort numeric scale
        effort_levels = {"fast": 0, "medium": 1, "deep": 2, "auto": 2}
        target_level = effort_levels.get(effort, 2)

        eligible_tool_ids = []
        for tool_id, tool in cap_map.items():
            if not tool.enabled:
                continue
            tool_min_level = effort_levels.get(tool.min_effort, 2)
            if tool_min_level <= target_level:
                eligible_tool_ids.append(tool_id)

        # Permission Check
        return await self.permissions.filter_tools(eligible_tool_ids, role=role)

    def _build_system_prompt(self, eligible_tools: list[str], effort: str) -> str:
        cap_map = get_capability_map()
        
        prompt_parts = [
            "You are the RIP Context Gateway Router & AI Assistant.",
            "Identity: Repository Intelligence Platform (RIP) powered by local Ollama Qwen2.5.",
            "Route queries to the right execution path and select appropriate tools."
        ]
        
        if effort == "deep":
            prompt_parts.append("INSTRUCTION: Be maximally inclusive. Select every eligible tool that could plausibly contribute to a complete answer.")
        else:
            prompt_parts.append("INSTRUCTION: Select only the minimum tools necessary to answer directly.")

        prompt_parts.append("\n## Tools Manifest")
        
        for tool_id in eligible_tools:
            tool = cap_map[tool_id]
            # Get the behavior for the requested effort, fallback to max available if lower
            eff = effort if effort in ["fast", "medium", "deep"] else "medium"
            if eff not in tool.behavior_by_effort:
                eff = tool.min_effort
            behavior = tool.behavior_by_effort.get(eff)
            if behavior:
                prompt_parts.append(f"- {tool_id}: {behavior.summary}")

        prompt_parts.append("\n## Paths")
        prompt_parts.append("- FAST (100ms): Active workspace project information, environment state, session/workspace memory, past activity, goals, chat history.")
        prompt_parts.append("- MEDIUM (2-5s): Code understanding, architecture, tracing, searching.")
        prompt_parts.append("- DEEP (30-120s): Complex multi-file edits, bug fixes, agent execution.")
        
        prompt_parts.append("\n## Output ONLY JSON")
        prompt_parts.append('{"path":"fast|medium|deep","confidence":0.0-1.0,"reasoning":"...","selected_tools":["tool_id_1","tool_id_2"],"needs_llm":true|false,"urgency":"low|normal|high"}')
        
        return "\n".join(prompt_parts)

    async def route(self, query: str, project_id: str | None, user_id: str | None, role: str, effort: str = "auto") -> RouteDecision:
        """Route a query to the right path with confidence gating."""
        logger.info("--- [ROUTER ENTRY] ---", query=query, project_id=project_id, user_role=role, effort=effort)
        
        # Stage 0: Deterministic Fast-Match
        fast_match = await self._stage_0_fast_match(query)
        if fast_match:
            fast_match.effort = effort
            logger.info("--- [ROUTER STAGE 0 MATCH] ---", path=fast_match.path, reasoning=fast_match.reasoning, selected_tools=fast_match.selected_tools)
            return fast_match

        normalized = self._normalize_query(query)
        cache_key = RouteCacheKey(
            normalized_query=f"{normalized}:{effort}",
            project_id=project_id or "none",
            workspace_id=project_id or "default",
            user_role=role,
        )
        
        # Stage 0.5: Semantic Cache
        cached = self._cache.get(cache_key)
        if cached is not None:
            cached.route_source = "cache"
            logger.info("--- [ROUTER CACHE HIT] ---", path=cached.path, reasoning=cached.reasoning)
            return cached

        try:
            user_role = UserRole(role)
        except ValueError:
            user_role = UserRole(settings.default_role)

        # Effort Gate
        eligible_tools = await self._effort_gate(effort, user_role)
        logger.info("--- [ROUTER EFFORT GATE] ---", effort=effort, eligible_tools_count=len(eligible_tools), eligible_tools=eligible_tools)
        system_prompt = self._build_system_prompt(eligible_tools, effort)

        try:
            context = await self._context.gather(project_id, user_id, role)
            decision = await asyncio.wait_for(self._call_llm(query, context, system_prompt), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.warning("--- [ROUTER LLM TIMEOUT] --- after %.1fs, falling back to precision rules", self.timeout)
            decision = self._fallback_route(query)
        except Exception as e:
            logger.error("--- [ROUTER LLM ERROR] --- %s, falling back to precision rules", e)
            decision = self._fallback_route(query)
            
        decision = self._apply_confidence_gating(decision)
        decision.effort = effort
        if not hasattr(decision, "route_source") or not decision.route_source:
            decision.route_source = "llm" if not decision.escalated else "llm (escalated)"
        
        self._cache.set(cache_key, decision)
        logger.info(
            "--- [ROUTER FINAL DECISION] ---",
            path=str(decision.path),
            confidence=decision.confidence,
            escalated=decision.escalated,
            route_source=decision.route_source,
            selected_tools=decision.selected_tools,
            reasoning=decision.reasoning,
        )
        return decision

    async def _call_llm(self, query: str, context: dict, system_prompt: str) -> RouteDecision:
        """Call the local LLM for routing decision."""
        context_str = json.dumps(context, default=str)[:1500]
        prompt = f"Query: {query}\n\nCurrent Context:\n{context_str}\n\nRoute this query and select tools. Return JSON only."
        try:
            from gateway.core.llm_pool.router import get_llm_router
            router = get_llm_router()
            config = await router.get_config(config_id=self.model)
            response = await router.query_llm(
                prompt=prompt, config=config, system_prompt=system_prompt, max_tokens=200
            )
            return self._parse_response(response)
        except Exception as e:
            logger.warning("LLM routing call failed: %s", e)
            raise

    def _fallback_route(self, query: str) -> RouteDecision:
        """Precision regex fallback when LLM is unavailable."""
        q = query.lower()
        if any(p in q for p in ["last in chat", "what was last", "previous chat", "what happened", "who changed", "why did we", "what's blocking", "summarize", "what goals", "my tasks", "what are my", "remind me", "what did we do"]):
            return RouteDecision(
                path=PathType.FAST,
                confidence=0.85,
                reasoning="Activity and chat recall query detected by fallback",
                suggested_sources=["workspace_memory", "workspace_knowledge", "git_history", "agent_runs"],
                selected_tools=["workspace_memory", "git_history", "agent_runs"],
                needs_llm=False,
                urgency="low",
                route_source="deterministic"
            )
        if any(p in q for p in ["/agent", "fix the", "fix this", "refactor", "migrate", "review pr", "deploy"]):
            return RouteDecision(
                path=PathType.DEEP,
                confidence=0.80,
                reasoning="Agent/action query detected by fallback",
                suggested_sources=["rip", "github", "workspace_memory", "workspace_knowledge"],
                selected_tools=["code_ast", "docker_terminal", "agent_runs"],
                needs_llm=True,
                urgency="high",
                route_source="deterministic"
            )
        return RouteDecision(
            path=PathType.MEDIUM,
            confidence=0.60,
            reasoning="Default fallback — safe middle ground",
            suggested_sources=["rip", "workspace_memory", "workspace_knowledge"],
            selected_tools=["code_ast"],
            needs_llm=False,
            urgency="normal",
            route_source="deterministic"
        )

    def _parse_response(self, response: str) -> RouteDecision:
        """Extract JSON from LLM response."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            match = re.search(r'\{[^{}]*"path"[^{}]*\}', response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return self._fallback_route("parse error")
            else:
                return self._fallback_route("parse error")
        try:
            path = PathType(data.get("path", "medium"))
        except ValueError:
            path = PathType.MEDIUM
        return RouteDecision(
            path=path,
            confidence=float(data.get("confidence", 0.5)),
            reasoning=str(data.get("reasoning", "")),
            suggested_sources=data.get("suggested_sources", ["rip"]),
            selected_tools=data.get("selected_tools", data.get("suggested_sources", ["rip"])),
            needs_llm=bool(data.get("needs_llm", False)),
            urgency=str(data.get("urgency", "normal")),
        )

    def _apply_confidence_gating(self, decision: RouteDecision) -> RouteDecision:
        """Escalate low-confidence routes."""
        thresholds = CONFIDENCE_THRESHOLDS.get(decision.path)
        if thresholds is None:
            return decision
        if decision.confidence >= thresholds["accept"]:
            return decision
        escalate_to = thresholds.get("escalate_to")
        if escalate_to and escalate_to != decision.path:
            logger.info("Escalating route: %s(%.2f) → %s", decision.path, decision.confidence, escalate_to)
            return RouteDecision(
                path=escalate_to,
                confidence=decision.confidence,
                reasoning=f"Escalated from {decision.path} due to low confidence ({decision.confidence:.0%})",
                suggested_sources=decision.suggested_sources,
                selected_tools=decision.selected_tools,
                needs_llm=decision.needs_llm or (escalate_to == PathType.DEEP),
                urgency=decision.urgency,
                escalated=True,
                escalated_from=decision.path.value,
            )
        if decision.path == PathType.DEEP and decision.confidence < thresholds["accept"]:
            return RouteDecision(
                path=PathType.DEEP,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
                suggested_sources=decision.suggested_sources,
                selected_tools=decision.selected_tools,
                needs_llm=True,
                urgency=decision.urgency,
                needs_clarification=True,
                suggested_interpretations=self._generate_clarifications(decision),
            )
        return decision

    def _generate_clarifications(self, decision: RouteDecision) -> list[str]:
        return ["Search the codebase for relevant files", "Check past decisions and patterns", "Run a full investigation with all sources"]

    def _normalize_query(self, query: str) -> str:
        q = query.lower().strip()
        q = re.sub(r'[^\w\s]', ' ', q)
        q = re.sub(r'\s+', ' ', q)
        return q.strip()

_router: RouterLLM | None = None
def get_router() -> RouterLLM:
    global _router
    if _router is None:
        _router = RouterLLM()
    return _router
