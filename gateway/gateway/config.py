from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_toml_settings() -> dict:
    """Load settings from .repo-intel/config.toml to match RIP's setup."""
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            return {}

    config_path = Path(".repo-intel/config.toml")
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
    except Exception:
        return {}

    flat = {}
    if "storage" in config_data:
        st = config_data["storage"]
        if "postgres_url" in st:
            flat["postgres_url"] = st["postgres_url"]
        if "redis_url" in st:
            flat["redis_url"] = st["redis_url"]
    if "llm" in config_data:
        llm = config_data["llm"]
        if "primary_provider" in llm:
            flat["llm_provider"] = llm["primary_provider"]
        if "primary_model" in llm:
            flat["llm_model"] = llm["primary_model"]
        if "google_api_key" in llm:
            flat["google_api_key"] = llm["google_api_key"]
        if "ollama_host" in llm:
            flat["ollama_host"] = llm["ollama_host"]
    return flat


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="GATEWAY_",
        case_sensitive=False,
        extra="allow"
    )
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8001
    version: str = "0.1.0"
    debug: bool = False
    
    # Database (reuse RIP's PostgreSQL) - match RIP's defaults
    postgres_url: str = "postgresql+asyncpg://repo_intel:repo_intel@localhost:5433/repo_intel?ssl=disable"
    redis_url: str = "redis://localhost:6379"
    
    # RIP MCP server
    rip_mcp_command: str = "uv"
    rip_mcp_args: list[str] = ["run", "python", "mcp/server.py"]
    rip_mcp_cwd: str = "."  # Path to RIP project (current directory since we're in RIP root)
    
    # GitHub MCP (optional)
    github_mcp_enabled: bool = False
    github_token: str = ""
    github_repo: str = ""
    github_api_url: str = "https://api.github.com"
    
    # Jira MCP (optional)
    jira_mcp_enabled: bool = False
    jira_url: str = ""
    jira_token: str = ""
    jira_email: str = ""
    jira_project_key: str = ""
    
    # Slack MCP (optional)
    slack_mcp_enabled: bool = False
    slack_token: str = ""
    slack_channel_id: str = ""
    
    # LLM for classifier fallback
    llm_provider: str = "google"
    llm_model: str = "gemini-2.5-flash"
    llm_fallback_threshold: float = 0.70
    google_api_key: str = ""
    ollama_host: str = "http://localhost:11434"
    
    # Token defaults
    default_max_tokens: int = 12000
    min_tokens_per_source: int = 500
    overhead_reserve_ratio: float = 0.10
    
    # Execution
    source_timeout_seconds: float = 120.0  # Increased to 2 minutes for RIP search commands
    circuit_breaker_threshold: int = 3
    circuit_breaker_reset_seconds: int = 300
    
    # LLM fallback
    llm_fallback_enabled: bool = False  # Disable by default since Ollama may not be running
    
    # Cache
    cache_ttl_seconds: int = 300
    
    # Permissions
    default_role: str = "developer"


def get_settings() -> GatewaySettings:
    """Get gateway settings, loading from .repo-intel/config.toml and .env to match RIP's setup."""
    import os
    toml_data = load_toml_settings()
    final_kwargs = {}
    for key, val in toml_data.items():
        # Check both with and without GATEWAY_ prefix for env vars
        env_val = os.environ.get(f"GATEWAY_{key.upper()}") or os.environ.get(key.upper()) or os.environ.get(key)
        if env_val is not None:
            final_kwargs[key] = env_val
        else:
            final_kwargs[key] = val
    return GatewaySettings(**final_kwargs)


settings = get_settings()
