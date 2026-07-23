"""Integration tests for workspace knowledge, memory, goals, entities."""
import pytest
from gateway.core.workspace.memory import get_workspace_memory
from gateway.core.workspace.knowledge import get_workspace_knowledge
from gateway.core.workspace.knowledge_scoring import compute_confidence, ConfidenceTier

@pytest.mark.asyncio
async def test_memory_records_and_searches():
    memory = get_workspace_memory()
    eid = await memory.record("test-ws", "execution", query="fix bug", summary="Fixed timeout")
    assert eid
    results = await memory.search("test-ws", "timeout")
    assert len(results) > 0

@pytest.mark.asyncio
async def test_knowledge_stores_and_approves():
    knowledge = get_workspace_knowledge()
    kid = await knowledge.store("test-ws", "decision", "Use SQLite", confidence=0.42, source_type="llm_suggestion")
    assert kid
    assert await knowledge.approve(kid)
    results = await knowledge.search("test-ws", "SQLite")
    assert len(results) > 0
    assert results[0]["confidence"] == 0.98

def test_confidence_human_approved():
    conf, tier = compute_confidence("llm_suggestion", human_override="approved")
    assert conf == 0.98
    assert tier == ConfidenceTier.APPROVED

def test_confidence_pattern_detection():
    conf, tier = compute_confidence("pattern_detection", frequency=14)
    assert 0.5 < conf < 0.8

def test_confidence_llm_suggestion():
    conf, tier = compute_confidence("llm_suggestion")
    assert conf < 0.5
    assert tier == ConfidenceTier.PENDING
