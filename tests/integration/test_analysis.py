from pathlib import Path

import pytest

from core.analysis.architecture_generator import ArchitectureGenerator
from core.analysis.coupling_analyser import CouplingAnalyser
from core.analysis.dead_code_detector import DeadCodeDetector
from core.analysis.onboard_engine import OnboardEngine
from core.analysis.risk_scorer import RiskScorer
from core.graph.builder import GraphBuilder
from core.graph.client import Neo4jClient
from core.graph.schema import setup_schema
from core.parser.languages.python import PythonParser

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password"
FIXTURE = Path("tests/fixtures/sample_repos/python_simple")


async def _client_or_skip() -> Neo4jClient:
    client = Neo4jClient(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        await client.connect()
    except Exception as exc:
        pytest.skip(f"Neo4j is not available: {exc}")
    return client


@pytest.mark.asyncio
async def test_analysis_engines_integration() -> None:
    client = await _client_or_skip()
    try:
        # Clear database and index the simple repo
        await client.execute("MATCH (n) DETACH DELETE n")
        await setup_schema(client)

        parser = PythonParser()
        builder = GraphBuilder(client)
        for relative in [
            "app.py",
            "services/user_service.py",
            "repositories/user_repository.py",
            "models/user.py",
        ]:
            path = FIXTURE / relative
            parsed = parser.parse_file(path, path.read_text(encoding="utf-8"))
            await builder.build_from_file(parsed)

        # Test DeadCodeDetector
        dead_detector = DeadCodeDetector(client)
        dead = await dead_detector.detect()
        assert isinstance(dead, list)

        # Test CouplingAnalyser
        coupling = CouplingAnalyser(client)
        all_coupling = await coupling.analyze_all()
        assert isinstance(all_coupling, list)

        # Test RiskScorer
        scorer = RiskScorer(client)
        all_risks = await scorer.get_all_risks()
        assert isinstance(all_risks, list)

        # Test OnboardEngine
        onboard = OnboardEngine(client)
        onboard_data = await onboard.generate_onboarding_data()
        assert "markdown" in onboard_data

        # Test ArchitectureGenerator
        arch_gen = ArchitectureGenerator(client)
        arch = await arch_gen.generate()
        assert "mermaid" in arch
        assert "services" in arch
    finally:
        await client.close()
