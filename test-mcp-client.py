
import httpx
import json

async def test_mcp_server():
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    
    try:
        # Test localhost first
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "http://localhost:8765",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"Localhost test status: {response.status_code}")
            print(f"Localhost response: {json.dumps(response.json(), indent=2)}")
            
        # Test local IP
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "http://10.140.111.45:8765",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            print(f"\nLocal IP test status: {response.status_code}")
            print(f"Local IP response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_mcp_server())

