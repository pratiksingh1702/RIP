import sys, asyncio
sys.path.insert(0, r"C:\Users\Dell\Downloads\RIP\gateway")
from gateway.core.sandbox.orchestrator import SandboxOrchestrator

async def main():
    orch = SandboxOrchestrator()
    await orch.update_sandbox_metadata("sandbox-default-c07290e6", name="Aider / Codex Sandbox", description="Contains aider/codex installation and test.py")
    print("Updated successfully")

if __name__ == "__main__":
    asyncio.run(main())
