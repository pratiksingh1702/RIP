"""Authority scorer."""


class AuthorityScorer:
    """Scores items based on source/query type authority."""

    AUTHORITY_SCORES = {
        "rip_trace": 0.95,
        "rip_impact": 0.90,
        "rip_architecture": 0.85,
        "rip_search": 0.75,
        "github_pr": 0.70,
        "github_commit": 0.60,
        "jira_ticket": 0.65,
        "slack_message": 0.50,
        "rip_git": 0.55,
    }

    def score(self, source: str, query_type: str) -> float:
        """Calculate authority score."""
        key = f"{source}_{query_type}"
        return self.AUTHORITY_SCORES.get(key, 0.5)
