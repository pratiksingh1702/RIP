"""Router LLM — Fast, local LLM for intelligent query routing."""
from __future__ import annotations
import asyncio
import json
import logging
import re
from gateway.core.router.models import PathType, RouteDecision, CONFIDENCE_THRESHOLDS
from gateway.core.router.context import get_routing_context
from gateway.core.router.cache import get_route_cache, RouteCacheKey
from gateway.config import settings

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """You are the Context Gateway Router. Route queries to the right execution path.

## Paths
- FAST (100ms): Past activity, decisions, goals, tasks, team status. NO codebase search, NO LLM.
- MEDIUM (2-5s): Code understanding, architecture, tracing, searching. RIP + optional LLM.
- DEEP (30-120s): Complex tasks, bug fixes, agent execution, PR reviews. Everything + full LLM.

## Rules
1. Past events/decisions/team → FAST
2. Understand/search code → MEDIUM  
3. Change code/run agents/complex analysis → DEEP
4. Casual greeting → FAST (return recent context)
5. Uncertain → MEDIUM (safe default)

## Output ONLY JSON
{"path":"fast|medium|deep","confidence":0.0-1.0,"reasoning":"...","needs_llm":true|false,"urgency":"low|normal|high","suggested_sources":["rip","workspace_memory"]}"""

class RouterLLM:
    """Routes queries to fast/medium/deep using a local LLM with 2s timeout."""

    def __init__(self):
        self.model = getattr(settings, 'router_model', None) or "ollama-local"
        self.timeout = getattr(settings, 'router_timeout', 2.0)
        self.fallback_threshold = getattr(settings, 'router_fallback_threshold', 0.70)
        self._context = get_routing_context()
        self._cache = get_route_cache()

    async def route(self, query: str, project_id: str | None, user_id: str | None, role: str) -> RouteDecision:
        """Route a query to the right path with confidence gating."""
        normalized = self._normalize_query(query)
        cache_key = RouteCacheKey(
            normalized_query=normalized,
            project_id=project_id or "none",
            workspace_id=project_id or "default",
            user_role=role,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            context = await self._context.gather(project_id, user_id, role)
            decision = await asyncio.wait_for(self._call_llm(query, context), timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.warning("Router LLM timed out after %.1fs, using fallback", self.timeout)
            decision = self._fallback_route(query)
        except Exception as e:
            logger.error("Router LLM failed: %s, using fallback", e)
            decision = self._fallback_route(query)
        decision = self._apply_confidence_gating(decision)
        self._cache.set(cache_key, decision)
        return decision

    async def _call_llm(self, query: str, context: dict) -> RouteDecision:
        """Call the local LLM for routing decision."""
        context_str = json.dumps(context, default=str)[:1500]
        prompt = f"Query: {query}\n\nCurrent Context:\n{context_str}\n\nRoute this query to fast/medium/deep. Return JSON only."
        try:
            from gateway.core.llm_pool.router import get_llm_router
            router = get_llm_router()
            config = await router.get_config(config_id=self.model)
            response = await router.query_llm(
                prompt=prompt, config=config, system_prompt=ROUTER_SYSTEM_PROMPT, max_tokens=200
            )
            return self._parse_response(response)
        except Exception as e:
            logger.warning("LLM routing call failed: %s", e)
            raise

    def _fallback_route(self, query: str) -> RouteDecision:
        """Precision regex fallback when LLM is unavailable."""
        q = query.lower()
        if any(p in q for p in ["what happened", "who changed", "why did we", "what's blocking", "summarize", "what goals", "my tasks", "what are my", "remind me"]):
            return RouteDecision(path=PathType.FAST, confidence=0.75, reasoning="Temporal/status query detected by fallback", suggested_sources=["workspace_memory", "workspace_knowledge"], needs_llm=False, urgency="low")
        if any(p in q for p in ["/agent", "fix the", "fix this", "refactor", "migrate", "review pr", "deploy"]):
            return RouteDecision(path=PathType.DEEP, confidence=0.80, reasoning="Agent/action query detected by fallback", suggested_sources=["rip", "github", "workspace_memory", "workspace_knowledge"], needs_llm=True, urgency="high")
        return RouteDecision(path=PathType.MEDIUM, confidence=0.60, reasoning="Default fallback — safe middle ground", suggested_sources=["rip", "workspace_memory", "workspace_knowledge"], needs_llm=False, urgency="normal")

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
