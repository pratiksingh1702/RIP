#!/usr/bin/env python3
"""Test just the context endpoint with detailed output."""

import asyncio
import httpx
import structlog
import traceback
import json

# Configure logging
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger(__name__)

GATEWAY_BASE_URL = "http://127.0.0.1:8001"


async def test_get_context():
    """Test get context endpoint."""
    logger.info("=" * 80)
    logger.info("TESTING: /api/context (with longer timeout)")
    logger.info("=" * 80)
    test_task = "Find server implementation"
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Calling /api/context with task:", test_task)
            response = await client.post(
                f"{GATEWAY_BASE_URL}/api/context",
                json={
                    "task": test_task,
                    "max_tokens": 10000,
                    "role": "developer"
                },
                timeout=300.0  # 5 minutes
            )
            logger.info(f"Get context status code: {response.status_code}")
            if response.status_code != 200:
                logger.error(f"Get context response text: {response.text}")
            assert response.status_code == 200, f"Get context failed: {response.status_code}"
            data = response.json()
            logger.info("✓ Get context passed!")
            print("\n" + "=" * 80)
            print("RESPONSE:")
            print("=" * 80)
            print(json.dumps(data, indent=2))
            
            if data.get("context"):
                print("\n" + "=" * 80)
                print("CONTEXT ITEMS:")
                print("=" * 80)
                for i, item in enumerate(data["context"]):
                    print(f"\n--- ITEM {i+1} (source: {item['source']}, type: {item['query_type']}, score: {item['score']}) ---")
                    print(item['content'])
            
            if data.get("warnings"):
                print("\n" + "=" * 80)
                print("WARNINGS:")
                print("=" * 80)
                for warning in data["warnings"]:
                    print(f"• {warning}")
            
            return data
        except Exception as e:
            logger.error(f"✗ Test get context failed: {traceback.format_exc()}")
            raise


async def run_test():
    await test_get_context()
    logger.info("\n🎉 Context test completed!")


if __name__ == "__main__":
    asyncio.run(run_test())
