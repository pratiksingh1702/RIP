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
            
        print(f"Checking {sandbox_id}...")
        try:
            # Check pip list
            exit_code, output = orch.exec_command(sandbox_id, "pip list | grep codex")
            if exit_code == 0 and 'codex' in output.lower():
                print(f"✅ FOUND via PIP in: {sandbox_id}")
                await orch.update_sandbox_metadata(sandbox_id, name="Codex Python Env", description="Contains Python Codex")
                continue
                
            # Check npm list
            exit_code, output = orch.exec_command(sandbox_id, "npm list -g | grep codex")
            if exit_code == 0 and 'codex' in output.lower():
                print(f"✅ FOUND via NPM in: {sandbox_id}")
                await orch.update_sandbox_metadata(sandbox_id, name="Codex Node Env", description="Contains Node Codex")
                continue
                
            # Check bash history
            exit_code, output = orch.exec_command(sandbox_id, "cat /root/.bash_history")
            if exit_code == 0 and 'codex' in output.lower():
                print(f"✅ FOUND via HISTORY in: {sandbox_id}")
                await orch.update_sandbox_metadata(sandbox_id, name="Codex Sandbox", description="Found codex commands in bash history")
                
        except Exception as e:
            pass

if __name__ == "__main__":
    asyncio.run(main())
