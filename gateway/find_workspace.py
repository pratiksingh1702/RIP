import sys, asyncio
sys.path.insert(0, r"C:\Users\Dell\Downloads\RIP\gateway")
from gateway.core.sandbox.orchestrator import SandboxOrchestrator

async def main():
    orch = SandboxOrchestrator()
    sandboxes = await orch.list_sandboxes(project_id='default', user_id='api-key:4')
    
    for sb in sandboxes:
        sandbox_id = sb['sandbox_id']
        status = sb['status']
        if status != 'running': continue
            
        exit_code, output = orch.exec_command(sandbox_id, "ls -la /workspace")
        if exit_code == 0:
            print(f"--- {sandbox_id} ---")
            print(output)

if __name__ == "__main__":
    asyncio.run(main())
