#!/usr/bin/env python3
"""Complete Gateway API Test Script."""

import asyncio
import httpx
import structlog
import traceback

# Configure logging
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

GATEWAY_BASE_URL = "http://127.0.0.1:8001"


async def test_health_check():
    """Test health check endpoint."""
    logger.info("Testing health check")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{GATEWAY_BASE_URL}/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        logger.info("Health check passed", response=data)
        return data


async def test_sources_list():
    """Test list sources endpoint."""
    logger.info("Testing sources list")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{GATEWAY_BASE_URL}/api/sources")
        assert response.status_code == 200, f"Sources list failed: {response.status_code}"
        data = response.json()
        logger.info("Sources list passed", response=data)
        return data


async def test_enable_source():
    """Test enable source endpoint."""
    logger.info("Testing enable source")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{GATEWAY_BASE_URL}/api/sources/github/enable")
            logger.info(f"Enable source status code: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Enable source response text: {response.text}")
            assert response.status_code == 200, f"Enable source failed: {response.status_code}"
            data = response.json()
            logger.info("Enable source passed", response=data)
            return data
        except Exception as e:
            logger.error(f"Test enable source failed with full traceback: {traceback.format_exc()}")
            raise


async def test_disable_source():
    """Test disable source endpoint."""
    logger.info("Testing disable source")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{GATEWAY_BASE_URL}/api/sources/github/disable")
            logger.info(f"Disable source status code: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Disable source response text: {response.text}")
            assert response.status_code == 200, f"Disable source failed: {response.status_code}"
            data = response.json()
            logger.info("Disable source passed", response=data)
            return data
        except Exception as e:
            logger.error(f"Test disable source failed with full traceback: {traceback.format_exc()}")
            raise


async def test_sessions_list():
    """Test list sessions endpoint."""
    logger.info("Testing sessions list")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{GATEWAY_BASE_URL}/api/sessions")
        assert response.status_code == 200, f"Sessions list failed: {response.status_code}"
        data = response.json()
        logger.info("Sessions list passed", response=data)
        return data


async def test_session_detail():
    """Test get session detail endpoint."""
    logger.info("Testing get session detail")
    async with httpx.AsyncClient() as client:
        # First get a list of sessions to get a session ID
        sessions_list = await test_sessions_list()
        if not sessions_list:
            logger.warning("No sessions found, skipping test")
            return None
        
        session_id = sessions_list[0]["id"]
        response = await client.get(f"{GATEWAY_BASE_URL}/api/sessions/{session_id}")
        assert response.status_code == 200, f"Get session detail failed: {response.status_code}"
        data = response.json()
        logger.info("Get session detail passed", response=data)
        return data


async def test_metrics():
    """Test metrics endpoint."""
    logger.info("Testing metrics")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{GATEWAY_BASE_URL}/api/metrics")
        assert response.status_code == 200, f"Metrics failed: {response.status_code}"
        data = response.json()
        logger.info("Metrics passed", response=data)
        return data


async def test_get_context():
    """Test get context endpoint."""
    logger.info("Testing get context")
    test_task = "Find server implementation"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GATEWAY_BASE_URL}/api/context",
                json={
                    "task": test_task,
                    "max_tokens": 5000,
                    "role": "developer"
                },
                timeout=120.0
            )
            logger.info(f"Get context status code: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Get context response text: {response.text}")
            assert response.status_code == 200, f"Get context failed: {response.status_code}"
            data = response.json()
            logger.info("Get context passed", response=data)
            return data
        except Exception as e:
            logger.error(f"Test get context failed with full traceback: {traceback.format_exc()}")
            raise


async def test_validate_change():
    """Test validate change endpoint."""
    logger.info("Testing validate change")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GATEWAY_BASE_URL}/api/validate",
                json={
                    "diff": "diff --git a/file.txt b/file.txt\n+ new line",
                    "files": ["file.txt"]
                },
                timeout=60.0
            )
            logger.info(f"Validate change status code: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Validate change response text: {response.text}")
            assert response.status_code == 200, f"Validate change failed: {response.status_code}"
            data = response.json()
            logger.info("Validate change passed", response=data)
            return data
        except Exception as e:
            logger.error(f"Test validate change failed with full traceback: {traceback.format_exc()}")
            raise


async def run_all_tests():
    """Run all API tests."""
    logger.info("Starting gateway API tests")
    
    tests = [
        test_health_check,
        test_sources_list,
        test_enable_source,
        test_disable_source,
        test_sessions_list,
        test_session_detail,
        test_metrics,
        test_get_context,
        test_validate_change
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
            logger.info(f"✅ Test passed: {test.__name__}")
        except Exception as e:
            failed += 1
            logger.error(f"❌ Test failed: {test.__name__}", error=str(e), traceback=traceback.format_exc())
    
    logger.info("All tests completed", passed=passed, failed=failed)
    
    if failed > 0:
        exit(1)
    else:
        logger.info("🎉 All tests passed!")
        exit(0)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
