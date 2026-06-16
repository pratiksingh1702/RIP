"""Server configuration."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    embedding_model: str = "all-MiniLM-L6-v2"
    top_k: int = 20
    postgres_url: str = "postgresql+asyncpg://repo_intel:repo_intel@localhost:5433/repo_intel"
    redis_url: str = "redis://localhost:6379"
    rip_server_host: str = Field(default="127.0.0.1", alias="RIP_SERVER_HOST")
    rip_server_port: int = Field(default=8000, alias="RIP_SERVER_PORT")
    llm_primary_provider: str = "ollama"
    llm_primary_model: str = "qwen2.5-coder:7b"
    llm_fallback_providers: list[str] = Field(
        default_factory=lambda: ["openrouter", "openai", "anthropic"]
    )
    llm_timeout: int = 60
    llm_max_tokens: int = 1500
    llm_temperature: float = 0.2
    llm_retry_count: int = 3
    llm_stream: bool = False
    ollama_host: str = "http://localhost:11434"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    azure_api_key: str | None = None
    azure_endpoint: str | None = None
    azure_api_version: str | None = None


def load_toml_settings() -> dict:
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
    if "graph" in config_data:
        g = config_data["graph"]
        if "neo4j_uri" in g:
            flat["neo4j_uri"] = g["neo4j_uri"]
        if "neo4j_user" in g:
            flat["neo4j_user"] = g["neo4j_user"]
        if "neo4j_password" in g:
            flat["neo4j_password"] = g["neo4j_password"]
    if "search" in config_data:
        s = config_data["search"]
        if "qdrant_host" in s:
            flat["qdrant_host"] = s["qdrant_host"]
        if "qdrant_port" in s:
            flat["qdrant_port"] = s["qdrant_port"]
        if "embedding_model" in s:
            flat["embedding_model"] = s["embedding_model"]
        if "top_k" in s:
            flat["top_k"] = s["top_k"]
    if "storage" in config_data:
        st = config_data["storage"]
        if "postgres_url" in st:
            flat["postgres_url"] = st["postgres_url"]
        if "redis_url" in st:
            flat["redis_url"] = st["redis_url"]
    if "server" in config_data:
        srv = config_data["server"]
        if "host" in srv:
            flat["rip_server_host"] = srv["host"]
        if "port" in srv:
            flat["rip_server_port"] = srv["port"]
    if "llm" in config_data:
        llm_config = config_data["llm"]
        if "primary_provider" in llm_config:
            flat["llm_primary_provider"] = llm_config["primary_provider"]
        if "primary_model" in llm_config:
            flat["llm_primary_model"] = llm_config["primary_model"]
        if "fallback_providers" in llm_config:
            flat["llm_fallback_providers"] = llm_config["fallback_providers"]
        if "timeout" in llm_config:
            flat["llm_timeout"] = llm_config["timeout"]
        if "max_tokens" in llm_config:
            flat["llm_max_tokens"] = llm_config["max_tokens"]
        if "temperature" in llm_config:
            flat["llm_temperature"] = llm_config["temperature"]
        if "retry_count" in llm_config:
            flat["llm_retry_count"] = llm_config["retry_count"]
        if "stream" in llm_config:
            flat["llm_stream"] = llm_config["stream"]
        if "ollama_host" in llm_config:
            flat["ollama_host"] = llm_config["ollama_host"]
        if "openai_api_key" in llm_config:
            flat["openai_api_key"] = llm_config["openai_api_key"]
        if "openai_base_url" in llm_config:
            flat["openai_base_url"] = llm_config["openai_base_url"]
        if "openrouter_api_key" in llm_config:
            flat["openrouter_api_key"] = llm_config["openrouter_api_key"]
        if "openrouter_base_url" in llm_config:
            flat["openrouter_base_url"] = llm_config["openrouter_base_url"]
        if "anthropic_api_key" in llm_config:
            flat["anthropic_api_key"] = llm_config["anthropic_api_key"]
        if "google_api_key" in llm_config:
            flat["google_api_key"] = llm_config["google_api_key"]
        if "groq_api_key" in llm_config:
            flat["groq_api_key"] = llm_config["groq_api_key"]
        if "azure_api_key" in llm_config:
            flat["azure_api_key"] = llm_config["azure_api_key"]
        if "azure_endpoint" in llm_config:
            flat["azure_endpoint"] = llm_config["azure_endpoint"]
        if "azure_api_version" in llm_config:
            flat["azure_api_version"] = llm_config["azure_api_version"]
    return flat


def get_settings() -> Settings:
    import os
    toml_data = load_toml_settings()
    final_kwargs = {}
    for key, val in toml_data.items():
        env_val = os.environ.get(key.upper()) or os.environ.get(key)
        if env_val is not None:
            final_kwargs[key] = env_val
        else:
            final_kwargs[key] = val
    return Settings(**final_kwargs)


def default_config_toml(repo_path: Path) -> str:
    project_name = repo_path.resolve().name
    root = repo_path.resolve().as_posix()
    return f"""[project]
name = "{project_name}"
root = "{root}"
languages = ["python", "java", "typescript"]
exclude = ["node_modules", "__pycache__", "*.min.js", "vendor/", "dist/"]

[indexing]
incremental = true
watch = false
max_file_size_kb = 500

[graph]
neo4j_uri = "bolt://localhost:7687"
neo4j_user = "neo4j"
neo4j_password = "password"
max_trace_depth = 15

[search]
qdrant_host = "localhost"
qdrant_port = 6333
embedding_model = "all-MiniLM-L6-v2"
# For higher quality at the cost of slower startup and larger downloads:
# embedding_model = "BAAI/bge-m3"
top_k = 20

[storage]
postgres_url = "postgresql+asyncpg://repo_intel:repo_intel@localhost:5433/repo_intel"
redis_url = "redis://localhost:6379"
use_sqlite = false

[llm]
primary_provider = "ollama"
primary_model = "qwen2.5-coder:7b"
fallback_providers = ["openrouter", "openai", "anthropic"]
timeout = 60
max_tokens = 1500
temperature = 0.2
retry_count = 3
stream = false
ollama_host = "http://localhost:11434"
# openai_api_key = "your-openai-api-key"
# openai_base_url = ""
# openrouter_api_key = "your-openrouter-api-key"
# openrouter_base_url = "https://openrouter.ai/api/v1"
# anthropic_api_key = "your-anthropic-api-key"
# google_api_key = "your-google-api-key"
# groq_api_key = "your-groq-api-key"
# azure_api_key = "your-azure-api-key"
# azure_endpoint = "your-azure-endpoint"
# azure_api_version = "2024-02-15-preview"
max_context_tokens = 6000
explain_by_default = false

[server]
host = "127.0.0.1"
port = 8000
auto_start = true
"""
