"""Block registry."""


from gateway.core.blocks.base import Block, BlockKind


class BlockRegistry:
    def __init__(self):
        self._blocks: dict[str, Block] = {}

    def register(self, block: Block):
        self._blocks[block.id] = block

    def get(self, block_id: str) -> Block | None:
        return self._blocks.get(block_id)

    def list(self, kind: BlockKind | None = None) -> list[Block]:
        if kind is None:
            return list(self._blocks.values())
        return [b for b in self._blocks.values() if b.kind == kind]


_registry = BlockRegistry()


def get_block_registry() -> BlockRegistry:
    return _registry
