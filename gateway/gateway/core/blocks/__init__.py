from gateway.core.blocks.base import Block, BlockKind, BlockResult, ExecutionContext
from gateway.core.blocks.context_retrieve import ContextRetrieveBlock
from gateway.core.blocks.data_blocks import DataExtractBlock, DataFilterBlock, DataMergeBlock, DataToJsonBlock
from gateway.core.blocks.filesystem import FSListDirectoryBlock, FSReadFileBlock, FSSearchFilesBlock, FSWriteFileBlock
from gateway.core.blocks.agent_block import AgentBlock
from gateway.core.blocks.fs_apply_patch import FSApplyPatchBlock
from gateway.core.blocks.flow import FlowDelayBlock, FlowLogBlock, FlowSetVariableBlock
from gateway.core.blocks.github_deployment import (
    GitHubCommitFilesBlock,
    GitHubCreateBranchBlock,
    GitHubOpenPrBlock,
)
from gateway.core.blocks.http import HTTPDeleteBlock, HTTPGetBlock, HTTPPostBlock, HTTPPutBlock
from gateway.core.blocks.notify import NotifyPushBlock, NotifySlackBlock, NotifyWebhookBlock
from gateway.core.blocks.prompt import ApprovalBlock, PromptAskAIBlock
from gateway.core.blocks.registry import BlockRegistry, get_block_registry
from gateway.core.blocks.rip_blocks import (
    RIPArchitectureBlock,
    RIPDeadCodeBlock,
    RIPExplainBlock,
    RIPImpactBlock,
    RIPMetricsBlock,
    RIPOnboardBlock,
    RIPSearchBlock,
    RIPTraceBlock,
)
from gateway.core.blocks.terminal import TerminalRunTestsBlock
from gateway.core.blocks.tool import ToolBlock
from gateway.core.sources.registry import get_source_registry


def register_all_blocks():
    """Register all available blocks."""
    registry = get_block_registry()

    # RIP blocks (granular)
    registry.register(RIPSearchBlock())
    registry.register(RIPTraceBlock())
    registry.register(RIPExplainBlock())
    registry.register(RIPImpactBlock())
    registry.register(RIPArchitectureBlock())
    registry.register(RIPMetricsBlock())
    registry.register(RIPDeadCodeBlock())
    registry.register(RIPOnboardBlock())

    # Gateway pipeline
    registry.register(ContextRetrieveBlock())

    # Terminal
    registry.register(TerminalRunTestsBlock())

    # AI + Approval
    registry.register(PromptAskAIBlock())
    registry.register(ApprovalBlock())

    # GitHub deployment
    registry.register(GitHubCreateBranchBlock())
    registry.register(GitHubCommitFilesBlock())
    registry.register(GitHubOpenPrBlock())

    # Filesystem
    registry.register(FSReadFileBlock())
    registry.register(FSWriteFileBlock())
    registry.register(FSListDirectoryBlock())
    registry.register(FSSearchFilesBlock())

    # HTTP
    registry.register(HTTPGetBlock())
    registry.register(HTTPPostBlock())
    registry.register(HTTPPutBlock())
    registry.register(HTTPDeleteBlock())

    # Data transform
    registry.register(DataFilterBlock())
    registry.register(DataExtractBlock())
    registry.register(DataMergeBlock())
    registry.register(DataToJsonBlock())

    # Notifications
    registry.register(NotifyPushBlock())
    registry.register(NotifySlackBlock())
    registry.register(NotifyWebhookBlock())

    # Flow control
    registry.register(FlowDelayBlock())
    registry.register(FlowSetVariableBlock())
    registry.register(FlowLogBlock())

    # Agent Runtime
    registry.register(AgentBlock())
    registry.register(FSApplyPatchBlock())

    # Register all MCP sources as tool blocks
    source_registry = get_source_registry()
    for source in source_registry.list_sources().values():
        registry.register(ToolBlock(source))


__all__ = [
    "Block", "BlockKind", "ExecutionContext", "BlockResult",
    "BlockRegistry", "get_block_registry",
    "register_all_blocks",
]

