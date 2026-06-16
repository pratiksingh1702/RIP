# ruff: noqa: E402
import sys
from pathlib import Path
from unittest.mock import MagicMock


# Mock sentence_transformers before any other imports to avoid loading torch/shm.dll
# and causing WinError 1455 (paging file too small).
class MockSentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass
    def encode(self, sentences, *args, **kwargs):
        import numpy as np
        if isinstance(sentences, str):
            return np.zeros(384)
        return np.zeros((len(sentences), 384))


class MockCrossEncoder:
    def __init__(self, *args, **kwargs):
        pass
    def predict(self, pairs, *args, **kwargs):
        import numpy as np
        return np.array([0.9 - 0.01 * i for i in range(len(pairs))])


mock_st = MagicMock()
mock_st.SentenceTransformer = MockSentenceTransformer
mock_st.CrossEncoder = MockCrossEncoder
sys.modules['sentence_transformers'] = mock_st


import pytest
from qdrant_client.http.exceptions import UnexpectedResponse

from core.graph.client import Neo4jClient
from core.indexer.pipeline import index_repository
from core.search.client import COLLECTION_NAME, QdrantClientWrapper
from core.search.embedder import EmbeddingPipeline
from core.search.reranker import CrossEncoderReranker
from core.search.searcher import Searcher

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
FIXTURE = Path("tests/fixtures/sample_repos/python_simple")


async def _services_or_skip():
    # check Neo4j
    graph = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        await graph.connect()
    except Exception as exc:
        pytest.skip(f"Neo4j not available: {exc}")

    # check Qdrant
    qdrant = QdrantClientWrapper(QDRANT_HOST, QDRANT_PORT)
    try:
        await qdrant.client.get_collection(COLLECTION_NAME)
    except UnexpectedResponse as exc:
        if exc.status_code == 404:
            pass
        else:
            await graph.close()
            pytest.skip(f"Qdrant not available: {exc}")
    except Exception as exc:
        await graph.close()
        pytest.skip(f"Qdrant not available: {exc}")

    return graph, qdrant


@pytest.mark.asyncio
async def test_indexing_and_hybrid_search() -> None:
    graph, qdrant = await _services_or_skip()
    try:
        # Clear Neo4j
        await graph.execute("MATCH (n) DETACH DELETE n")

        # Clear Qdrant collection if exists, then initialize
        try:
            await qdrant.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        await qdrant.init_collection()

        # 1. Run pipeline indexing
        summary = await index_repository(FIXTURE, graph)
        assert summary.indexed_files > 0
        assert summary.total_entities > 0

        # Check Qdrant collection size
        collection_info = await qdrant.client.get_collection(COLLECTION_NAME)
        points_count = collection_info.points_count
        assert points_count > 0

        # 2. Run hybrid search
        embedder = EmbeddingPipeline()
        reranker = CrossEncoderReranker()
        searcher = Searcher(qdrant, embedder, reranker, graph)

        results = await searcher.hybrid_search(
            query="retrieve user details or look up user from database",
            top_k=5
        )
        assert len(results) > 0
        # The top score result should be user-related since we mock the scores
        assert results[0].score > 0

        # 3. Check for duplicates upon re-indexing
        await index_repository(FIXTURE, graph)
        collection_info_2 = await qdrant.client.get_collection(COLLECTION_NAME)
        assert collection_info_2.points_count == points_count

    finally:
        await graph.close()
        await qdrant.close()
