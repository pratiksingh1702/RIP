#!/usr/bin/env python3
"""Quick gateway health check script."""

import asyncio
import httpx


async def check_health():
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("http://127.0.0.1:8001/health")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")


asyncio.run(check_health())
