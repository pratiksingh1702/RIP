"""Planner strategy table."""

from gateway.core.classifier.models import IntentType


STRATEGY_TABLE = {
    IntentType.BUG_FIX: {
        "always_query": [
            {"source": "rip", "type": "trace", "description": "call chain around the error"},
            {"source": "rip", "type": "search", "description": "similar error handling patterns"},
            {"source": "rip", "type": "impact", "description": "what depends on the error area"},
        ],
        "conditional_query": [
            {
                "source": "github",
                "type": "recent_commits",
                "condition": "files_overlap_with_active_prs",
                "description": "files changed recently"
            },
            {
                "source": "jira",
                "type": "ticket",
                "condition": "ticket_number_in_task",
                "description": "bug report ticket"
            },
        ],
        "skip": ["slack"],
        "token_weights": {"rip": 0.55, "github": 0.30, "jira": 0.15},
        "recency_boost": True,
    },

    IntentType.FEATURE_ADDITION: {
        "always_query": [
            {"source": "rip", "type": "architecture", "description": "existing patterns"},
            {"source": "rip", "type": "search", "description": "similar existing implementations"},
            {"source": "rip", "type": "impact", "description": "what will be affected"},
        ],
        "conditional_query": [
            {
                "source": "jira",
                "type": "ticket",
                "condition": "ticket_number_in_task",
                "description": "feature requirements and acceptance criteria"
            },
            {
                "source": "github",
                "type": "similar_prs",
                "condition": "always",
                "description": "similar features implemented before"
            },
        ],
        "skip": ["slack"],
        "token_weights": {"rip": 0.50, "github": 0.25, "jira": 0.25},
        "recency_boost": False,
    },

    IntentType.ARCHITECTURAL_QUESTION: {
        "always_query": [
            {"source": "rip", "type": "architecture", "description": "full architecture map"},
            {"source": "rip", "type": "trace", "description": "call chains"},
        ],
        "conditional_query": [
            {
                "source": "slack",
                "type": "search",
                "condition": "always",
                "description": "team discussions about this area"
            },
            {
                "source": "github",
                "type": "pr_descriptions",
                "condition": "always",
                "description": "PR descriptions explaining design choices"
            },
        ],
        "skip": [],
        "token_weights": {"rip": 0.45, "github": 0.25, "slack": 0.30},
        "recency_boost": False,
    },

    IntentType.REFACTOR: {
        "always_query": [
            {"source": "rip", "type": "impact", "description": "everything that depends on target"},
            {"source": "rip", "type": "search", "description": "existing patterns to match"},
        ],
        "conditional_query": [
            {
                "source": "github",
                "type": "recent_commits",
                "condition": "always",
                "description": "recent changes to affected files"
            },
        ],
        "skip": ["slack", "jira"],
        "token_weights": {"rip": 0.70, "github": 0.30},
        "recency_boost": False,
    },

    IntentType.INVESTIGATION: {
        "always_query": [
            {"source": "rip", "type": "search", "description": "search for relevant code"},
            {"source": "rip", "type": "trace", "description": "call chains through the area"},
        ],
        "conditional_query": [
            {"source": "github", "type": "recent_commits", "condition": "always", "description": "recent history"}
        ],
        "skip": ["slack", "jira"],
        "token_weights": {"rip": 0.60, "github": 0.40},
        "recency_boost": True,
    },

    IntentType.DOCUMENTATION: {
        "always_query": [
            {"source": "rip", "type": "search", "description": "find relevant code"},
            {"source": "rip", "type": "architecture", "description": "module structure"},
        ],
        "conditional_query": [],
        "skip": ["github", "jira", "slack"],
        "token_weights": {"rip": 1.00},
        "recency_boost": False,
    },
}
