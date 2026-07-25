"""Query Router — Classifies and routes queries to fast/medium/deep paths."""
from gateway.core.router.models import RouteDecision, RouteCacheKey, RouteCacheEntry, PathType
from gateway.core.router.llm_router import RouterLLM, get_router
from gateway.core.router.cache import RouteCache, get_route_cache
from gateway.core.router.context import RoutingContextGatherer, get_routing_context
from gateway.core.router.feedback import RouteFeedbackLogger, get_route_feedback

__all__ = [
    "RouteDecision", "RouteCacheKey", "RouteCacheEntry", "PathType",
    "RouterLLM", "get_router",
    "RouteCache", "get_route_cache",
    "RoutingContextGatherer", "get_routing_context",
    "RouteFeedbackLogger", "get_route_feedback",
]
