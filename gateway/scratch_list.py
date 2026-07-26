import sys
import asyncio
sys.path.insert(0, r"C:\Users\Dell\Downloads\RIP\gateway")
from gateway.core.sandbox.orchestrator import SandboxOrchestrator

async def main():
    try:
        orch = SandboxOrchestrator()
        sandboxes = await orch.list_sandboxes(project_id='default', user_id='api-key:4')
        print("Success:", sandboxes)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
