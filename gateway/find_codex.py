import sys, asyncio
sys.path.insert(0, r"C:\Users\Dell\Downloads\RIP\gateway")
from gateway.core.sandbox.orchestrator import SandboxOrchestrator

async def main():
    orch = SandboxOrchestrator()
    sandboxes = await orch.list_sandboxes(project_id='default', user_id='api-key:4')
    
    print(f"Found {len(sandboxes)} sandboxes. Checking for codex...")
    for sb in sandboxes:
        sandbox_id = sb['sandbox_id']
        status = sb['status']
        if status != 'running':
            continue
            
        print(f"Checking {sandbox_id}...")
        try:
            # Execute command to find codex
            exit_code, output = orch.exec_command(sandbox_id, "which codex")
            if exit_code == 0 and output.strip():
                print(f"✅ FOUND CODEX IN: {sandbox_id}")
                print(f"  Path: {output.strip()}")
                # Automatically update its metadata!
                await orch.update_sandbox_metadata(sandbox_id, name="Codex Sandbox", description="Pre-installed with Codex")
                print("  Metadata updated successfully!")
            else:
                pass # not found
        except Exception as e:
            print(f"Error checking {sandbox_id}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
