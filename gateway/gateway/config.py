from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GATEWAY_",
        case_sensitive=False,
        extra="allow"
    )
    
    # Server
    host: str = "127.0.0.1"
    port: int = 8001
    version: str = "0.1.0"
    
    # Database (reuse RIP's PostgreSQL)
    postgres_url: str = "postgresql+asyncpg://rip_user:rip_pass@localhost:5432/rip_db"
    redis_url: str = "redis://localhost:6379/1"  # Different DB from RIP
    
    # RIP MCP server
    rip_mcp_command: str = "uv"
    rip_mcp_args: list[str] = ["run", "python", "mcp/server.py"]
    rip_mcp_cwd: str = "../"  # Path to RIP project
    
    # GitHub MCP (optional)
    github_mcp_enabled: bool = False
    github_token: str = ""
    
    # Jira MCP (optional)
    jira_mcp_enabled: bool = False
    jira_url: str = ""
    jira_token: str = ""
    
    # Slack MCP (optional)
    slack_mcp_enabled: bool = False
    slack_token: str = ""
    
    # LLM for classifier fallback
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5-coder:7b"
    llm_fallback_threshold: float = 0.70
    
    # Token defaults
    default_max_tokens: int = 12000
    min_tokens_per_source: int = 500
    overhead_reserve_ratio: float = 0.10
    
    # Execution
    source_timeout_seconds: float = 5.0
    circuit_breaker_threshold: int = 3
    circuit_breaker_reset_seconds: int = 300
    
    # Cache
    cache_ttl_seconds: int = 300
    
    # Permissions
    default_role: str = "developer"


settings = GatewaySettings()
