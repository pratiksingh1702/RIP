"""Explain command."""

from __future__ import annotations

import asyncio
import logging

from rich.console import Console

from core.graph.client import Neo4jClient
from core.llm.client import query_llm
from core.llm.context_assembler import ContextAssembler
from core.llm.prompts.explain import EXPLAIN_SYSTEM_PROMPT, EXPLAIN_USER_PROMPT
from core.projects import resolve_project_id
from core.search.client import QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline, embedding_dimension
from core.search.reranker import CrossEncoderReranker
from core.search.searcher import Searcher
from server.config import get_settings

console = Console()
logger = logging.getLogger(__name__)


def _console_safe(text: str) -> str:
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
    except UnicodeEncodeError:
        return text.encode(encoding, errors="replace").decode(encoding)
    return text


def explain(
    symbol: str,
    context_level: str = "file",
    provider: str | None = None,
    model: str | None = None,
    project: str | None = None,
) -> None:
    """Explain a code symbol using LLM analysis."""
    asyncio.run(
        _explain(
            symbol=symbol,
            context_level=context_level,
            provider=provider,
            model=model,
            project=project,
        )
    )


async def _explain(
    symbol: str,
    context_level: str,
    provider: str | None = None,
    model: str | None = None,
    project: str | None = None,
) -> None:
    settings = get_settings()
    project_id = resolve_project_id(project)
    client = Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    qdrant_client = QdrantClientWrapper(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        vector_size=embedding_dimension(settings.embedding_model),
    )
    try:
        # Step 1: Always start with hybrid search for natural language queries
        console.print(f"[yellow]🔍 Searching repository for: '{symbol}'...[/yellow]")
        logger.info("Starting hybrid search for query: '%s'", symbol)
        searcher = Searcher(
            qdrant_client=qdrant_client,
            embedder=EmbeddingPipeline(model_name=settings.embedding_model),
            reranker=CrossEncoderReranker(),
            graph_client=client,
        )
        results = await searcher.hybrid_search(symbol, top_k=10, project_id=project_id)
        logger.info("Hybrid search returned %s results", len(results))
        
        assembler = ContextAssembler(client, project_id=project_id)
        
        if results:
            console.print(f"[dim]→ Found {len(results)} relevant components! Assembling context...[/dim]")
            context_data = await assembler.assemble_search_context(symbol, results)
            logger.info("Assembled search context successfully")
        else:
            # Fallback to symbol lookup if no search results
            console.print(f"[dim]→ No semantic results found! Trying direct symbol lookup for '{symbol}'...[/dim]")
            logger.info("No hybrid search results, falling back to exact symbol lookup")
            context_data = await assembler.assemble_context(symbol, context_level)
        
        if not context_data.get("found"):
            console.print(
                _console_safe(context_data["context_str"]),
                style="yellow",
                markup=False,
            )
            return

        # Query LLM
        context_str = _console_safe(context_data["context_str"])
        prompt = EXPLAIN_USER_PROMPT.format(context=context_str)
        provider_info = f" (Provider: {provider}, Model: {model})" if provider or model else ""
        console.print(f"[yellow]🤖 Generating explanation for: {symbol}...{provider_info}[/yellow]")
        logger.info("Calling LLM for explanation")
        explanation = await query_llm(
            prompt,
            system_prompt=EXPLAIN_SYSTEM_PROMPT,
            provider=provider,
            model=model,
        )
        if explanation.startswith("[Fallback Explanation due to LLM error:"):
            console.print("\n[bold red]⚠️  LLM Error[/bold red]\n")
            # Extract the error from the fallback string
            if "LLM error:" in explanation:
                error_part = explanation.split("LLM error:", 1)[1].split("\n", 1)[0].strip()
                console.print(f"[red]Error: {error_part}[/red]\n")
                # Check if it's an API key issue
                if "API key" in error_part.lower() or "no api key" in error_part.lower():
                    console.print(
                        "[yellow]💡  Tip: Please configure your API key in "
                        ".repo-intel/config.toml[/yellow]\n"
                    )
            console.print("[yellow]Falling back to raw context...[/yellow]\n")
            console.print(context_str, markup=False)
            return

        console.print("\n")
        console.print(_console_safe(explanation), markup=False)
    finally:
        await qdrant_client.close()
        await client.close()
