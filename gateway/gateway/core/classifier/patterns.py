"""Keyword patterns for intent classification and domain detection."""


# Intent type keywords
INTENT_KEYWORDS: dict[str, list[str]] = {
    "bug_fix": [
        "fix", "bug", "error", "issue", "crash", "fail", "broken", "problem",
        "resolve", "repair", "debug", "null pointer", "exception", "stack trace"
    ],
    "feature_addition": [
        "add", "create", "implement", "new", "feature", "enhance", "improve",
        "build", "develop", "introduce", "extend", "expand", "upgrade"
    ],
    "refactor": [
        "refactor", "clean up", "restructure", "reorganize", "optimize",
        "improve code", "simplify", "tidy", "rework", "rewrite"
    ],
    "architectural_question": [
        "how", "what", "why", "explain", "architecture", "design",
        "understand", "documentation", "overview", "structure", "pattern"
    ],
    "investigation": [
        "investigate", "explore", "research", "analyze", "trace", "find",
        "locate", "inspect", "examine", "study", "check"
    ],
    "documentation": [
        "document", "doc", "write docs", "update docs", "readme",
        "comment", "annotate", "explain"
    ]
}

# Domain detection keywords
DOMAIN_PATTERNS: dict[str, list[str]] = {
    "payment": [
        "payment", "stripe", "charge", "invoice", "billing", "refund",
        "transaction", "credit card", "checkout", "subscription"
    ],
    "auth": [
        "auth", "authentication", "login", "jwt", "token", "session",
        "permission", "oauth", "password", "security", "user"
    ],
    "api": [
        "endpoint", "route", "request", "response", "http", "rest",
        "graphql", "api", "websocket", "client"
    ],
    "database": [
        "query", "migration", "schema", "model", "orm", "repository",
        "table", "sql", "database", "db", "postgres", "mysql"
    ],
    "notification": [
        "email", "sms", "push", "notification", "webhook", "event",
        "alert", "message"
    ],
    "infrastructure": [
        "deploy", "docker", "kubernetes", "ci", "pipeline", "server",
        "infra", "cloud", "aws", "gcp", "azure", "container"
    ]
}

# Stop words to exclude from pattern matching
STOP_WORDS: set = {
    "the", "a", "an", "is", "in", "to", "for", "of", "with", "and",
    "but", "or", "on", "at", "by", "from", "up", "about", "into",
    "over", "after"
}
