"""Explain command - architecture-aware with visual diagrams."""

from __future__ import annotations

import asyncio
import logging

from rich.console import Console
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table

from core.graph.client import Neo4jClient
from core.graph.queries.trace import trace_workflow_chain
from core.graph.queries.impact import dependency_graph as get_dependency_graph
from core.llm.client import query_llm
from core.llm.context_assembler import ContextAssembler
from core.llm.models import ExplainContext
from core.llm.prompts.explain import get_explain_prompt
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


def _safe_print(text: str, **kwargs) -> None:
    console.print(_console_safe(text), **kwargs)


def explain(
    symbol: str,
    context_level: str = "file",
    provider: str | None = None,
    model: str | None = None,
    project: str | None = None,
    diagram: bool = False,        # NEW: Show Mermaid diagram
    tree_view: bool = False,       # NEW: Show Rich tree view
    dependencies: bool = False,    # NEW: Show dependency graph table
    no_llm: bool = False,          # NEW: Skip LLM, just show graph
    max_hops: int = 8,             # NEW: Max hops for workflow trace
) -> None:
    """Explain a code symbol with architecture-aware analysis.
    
    Args:
        symbol: What to explain (can be natural language query)
        context_level: Context scope
        provider: LLM provider override
        model: LLM model override
        project: Project ID
        diagram: Show Mermaid diagram
        tree_view: Show Rich tree visualization
        dependencies: Show dependency table
        no_llm: Skip LLM, show graph analysis only
        max_hops: Maximum hops for workflow tracing
    """
    asyncio.run(
        _explain(
            symbol=symbol,
            context_level=context_level,
            provider=provider,
            model=model,
            project=project,
            diagram=diagram,
            tree_view=tree_view,
            dependencies=dependencies,
            no_llm=no_llm,
            max_hops=max_hops,
        )
    )


async def _explain(
    symbol: str,
    context_level: str,
    provider: str | None = None,
    model: str | None = None,
    project: str | None = None,
    diagram: bool = False,
    tree_view: bool = False,
    dependencies: bool = False,
    no_llm: bool = False,
    max_hops: int = 8,
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
        # Step 1: Detect intent
        assembler = ContextAssembler(client, project_id=project_id)
        intent = assembler.detect_intent(symbol)
        
        _safe_print(f"[yellow]Analyzing: '{symbol}'...[/yellow]")
        _safe_print(f"[dim]-> Detected intent: {intent.value}[/dim]")
        
        # Step 2: Hybrid search
        searcher = Searcher(
            qdrant_client=qdrant_client,
            embedder=EmbeddingPipeline(model_name=settings.embedding_model),
            reranker=CrossEncoderReranker(),
            graph_client=client,
        )
        results = await searcher.hybrid_search(symbol, top_k=10, project_id=project_id)
        
        # Step 3: Assemble architectural context
        ctx = await assembler.assemble_context(symbol, context_level, search_results=results)
        
        if not ctx.found:
            console.print(ctx.context_str, style="yellow", markup=False)
            return
        
        # Step 4: Generate visual graphs from Neo4j (not LLM)
        if diagram or tree_view:
            _show_workflow_diagram(ctx, diagram=diagram, tree_view=tree_view)
        
        if dependencies:
            _show_dependency_table(ctx)
        
        # Step 5: Show key info panel
        _show_info_panel(ctx)
        
        # Step 6: LLM Explanation (unless --no-llm)
        if not no_llm:
            _safe_print("[yellow]Generating explanation...[/yellow]")
            
            system_prompt, user_prompt = get_explain_prompt(
                intent.value, symbol, ctx.context_str
            )
            
            explanation = await query_llm(
                user_prompt,
                system_prompt=system_prompt,
                provider=provider,
                model=model,
            )
            
            if explanation.startswith("[Fallback Explanation due to LLM error:"):
                _safe_print("\n[bold red]LLM Error - showing graph analysis instead[/bold red]\n")
                _show_fallback_context(ctx)
            else:
                console.print("\n")
                console.print(_console_safe(explanation), markup=False)
        else:
            _safe_print("[dim]-> LLM skipped (--no-llm flag)[/dim]")
            _show_fallback_context(ctx)
        
        # Step 7: Suggestions
        if ctx.suggestions:
            _safe_print("\n[bold cyan]Suggestions:[/bold cyan]")
            for s in ctx.suggestions:
                _safe_print(f"  - {s}")
        
    finally:
        await qdrant_client.close()
        await client.close()


def _show_workflow_diagram(ctx: ExplainContext, diagram: bool = False, tree_view: bool = False):
    """Show workflow as Mermaid diagram and/or Rich tree."""
    
    if tree_view and ctx.workflow_chain:
        _safe_print("\n[bold cyan]Workflow Tree:[/bold cyan]")
        root_name = ctx.query[:30]
        tree = Tree(f"[bold yellow]{root_name}[/bold yellow]")
        
        # Build tree from workflow chain
        nodes_added = {}
        # Find the root node (first "from" in workflow chain)
        if ctx.workflow_chain:
            first_hop = ctx.workflow_chain[0]
            root_node = first_hop.get("from") or first_hop.get("name", "?")
            if root_node not in nodes_added:
                nodes_added[root_node] = tree.add(f"[cyan]{root_node}[/cyan]")
        
        for hop in ctx.workflow_chain[:15]:
            from_n = hop.get("from") or hop.get("name", "?")
            to_n = hop.get("to", "")
            rel = hop.get("relationship", "")
            
            if from_n not in nodes_added:
                nodes_added[from_n] = tree.add(f"[cyan]{from_n}[/cyan]")
            
            if to_n and to_n not in nodes_added:
                label = f"[green]{to_n}[/green] [dim]({rel})[/dim]"
                nodes_added[to_n] = nodes_added[from_n].add(label)
        
        console.print(tree)
    
    if diagram and ctx.workflow_chain:
        _safe_print("\n[bold cyan]Mermaid Diagram:[/bold cyan]")
        mermaid = _generate_mermaid(ctx)
        console.print(mermaid)
        _safe_print("[dim]-> Paste this into https://mermaid.live to visualize[/dim]")


def _generate_mermaid(ctx: ExplainContext) -> str:
    """Generate Mermaid flowchart from context."""
    lines = ["```mermaid", "graph TD"]
    seen = set()
    
    # Add workflow chain edges
    for hop in ctx.workflow_chain[:20]:
        from_n = (hop.get("from") or hop.get("name", "?")).replace('"', "'")[:30]
        to_n = (hop.get("to", "")).replace('"', "'")[:30]
        rel = hop.get("relationship", "RELATED")
        
        if to_n:
            edge = f'    {from_n} -->|{rel}| {to_n}'
            if edge not in seen:
                seen.add(edge)
                lines.append(edge)
    
    # Add dependency graph edges (only from the dependency_graph dict)
    for name, deps in list(ctx.dependency_graph.items())[:10]:
        name_clean = name.replace('"', "'")[:30]
        for dep_name, rel_type in deps[:3]:
            dep_clean = dep_name.replace('"', "'")[:30]
            edge = f'    {name_clean} -->|{rel_type}| {dep_clean}'
            if edge not in seen:
                seen.add(edge)
                lines.append(edge)
    
    lines.append("```")
    return "\n".join(lines)


def _show_dependency_table(ctx: ExplainContext):
    """Show dependency graph as a Rich table."""
    if not ctx.dependency_graph:
        return
    
    _safe_print("\n[bold cyan]Dependency Graph:[/bold cyan]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Component")
    table.add_column("Relationship")
    table.add_column("Target")
    
    for name, deps in list(ctx.dependency_graph.items())[:15]:
        for dep_name, rel_type in deps[:3]:
            table.add_row(name, rel_type, dep_name)
    
    console.print(table)


def _show_info_panel(ctx: ExplainContext):
    """Show key information panel."""
    content = []
    
    if ctx.overview:
        content.append(f"[bold]Overview:[/bold] {ctx.overview}")
    
    if ctx.feature:
        content.append(f"[bold]Feature:[/bold] {ctx.feature}")
    
    if ctx.important_entities:
        content.append(f"[bold]Key Entities:[/bold] {len(ctx.important_entities)} found")
    
    if ctx.api_endpoints:
        content.append(f"[bold]API Endpoints:[/bold] {len(ctx.api_endpoints)} found")
    
    if ctx.state_flow:
        content.append(f"[bold]State Flow:[/bold] {len(ctx.state_flow)} steps")
    
    if content:
        console.print(Panel("\n".join(content), title="Analysis Summary", border_style="cyan"))


def _show_fallback_context(ctx: ExplainContext):
    """Show raw context when LLM fails."""
    if ctx.workflow_chain:
        console.print("[bold]Workflow Chain:[/bold]")
        # Build a proper chain
        chain_parts = []
        seen = set()
        for hop in ctx.workflow_chain[:10]:
            from_n = hop.get("from") or hop.get("name", "?")
            to_n = hop.get("to", "")
            if from_n not in seen:
                chain_parts.append(from_n)
                seen.add(from_n)
            if to_n and to_n not in seen:
                chain_parts.append(to_n)
                seen.add(to_n)
        chain = " -> ".join(chain_parts)
        _safe_print(f"  {chain}")
    
    if ctx.important_files:
        console.print("\n[bold]Important Files:[/bold]")
        for f in ctx.important_files[:5]:
            _safe_print(f"  - {f}")
    
    if ctx.important_entities:
        console.print("\n[bold]Key Entities:[/bold]")
        for e in ctx.important_entities[:5]:
            _safe_print(f"  - {e.get('name')} ({e.get('type')}) - {e.get('file_path')}")
