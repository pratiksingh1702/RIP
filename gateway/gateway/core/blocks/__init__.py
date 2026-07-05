from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.blocks.context_retrieve import ContextRetrieveBlock
from gateway.core.blocks.github_deployment import (
    GitHubCommitFilesBlock,
    GitHubCreateBranchBlock,
    GitHubOpenPrBlock,
)
from gateway.core.blocks.prompt import ApprovalBlock, PromptAskAIBlock
from gateway.core.blocks.registry import BlockRegistry, get_block_registry
from gateway.core.blocks.terminal import TerminalRunTestsBlock
from gateway.core.blocks.tool import ToolBlock
from gateway.core.sources.registry import get_source_registry


def register_all_blocks():
    """Register all available blocks."""
    registry = get_block_registry()
    registry.register(ContextRetrieveBlock())
    registry.register(TerminalRunTestsBlock())
    registry.register(PromptAskAIBlock())
    registry.register(ApprovalBlock())
    registry.register(GitHubCreateBranchBlock())
    registry.register(GitHubCommitFilesBlock())
    registry.register(GitHubOpenPrBlock())
    
    # Register all sources as tool blocks
    source_registry = get_source_registry()
    for source in source_registry.list_sources().values():
        registry.register(ToolBlock(source))


__all__ = [
    "Block",
    "BlockKind",
    "ExecutionContext",
    "BlockResult",
    "BlockRegistry",
    "get_block_registry",
    "ContextRetrieveBlock",
    "TerminalRunTestsBlock",
    "PromptAskAIBlock",
    "ApprovalBlock",
    "GitHubCreateBranchBlock",
    "GitHubCommitFilesBlock",
    "GitHubOpenPrBlock",
    "register_all_blocks",
]
