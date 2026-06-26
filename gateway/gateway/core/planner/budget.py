"""Token budget allocation for the planner."""

from gateway.config import settings


def allocate_token_budget(
    total_budget: int,
    token_weights: dict[str, float],
    enabled_sources: list[str]
) -> dict[str, int]:
    """
    Allocate token budget to sources based on weights.

    Reserves a portion for overhead and ensures each source gets a minimum.
    """
    # Reserve overhead
    overhead = int(total_budget * settings.overhead_reserve_ratio)
    available = total_budget - overhead

    # Filter weights to only enabled sources
    filtered_weights = {
        s: w for s, w in token_weights.items()
        if s in enabled_sources
    }

    if not filtered_weights:
        # Fallback to RIP only
        return {"rip": available}

    # Normalize weights
    total_weight = sum(filtered_weights.values())
    normalized = {s: w / total_weight for s, w in filtered_weights.items()}

    # Allocate, ensuring minimum per source
    allocations = {}
    used = 0

    # First pass: minimum tokens
    for source in normalized:
        alloc = max(settings.min_tokens_per_source, int(available * normalized[source]))
        allocations[source] = alloc
        used += alloc

    # Adjust if we went over (shouldn't happen with reasonable min)
    if used > available:
        # Reduce proportionally
        ratio = available / used
        for source in allocations:
            allocations[source] = max(settings.min_tokens_per_source, int(allocations[source] * ratio))

    return allocations
