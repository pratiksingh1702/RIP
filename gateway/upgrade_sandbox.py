import sys, asyncio, datetime
sys.path.insert(0, r"C:\Users\Dell\Downloads\RIP\gateway")
from gateway.core.sandbox.orchestrator import SandboxOrchestrator

async def main():
    orch = SandboxOrchestrator()
    sandbox_id = "sandbox-default-c07290e6"
    client = orch.client
    
    print("1. Committing old sandbox to image...")
    container = client.containers.get(sandbox_id)
    container.commit(repository="rip-sandbox-backup", tag="latest")
    
    print("2. Stopping and renaming old sandbox...")
    try:
        container.stop()
    except Exception as e:
        print("Stop error (ignoring):", e)
    container.rename(sandbox_id + "-old")
    
    print("3. Creating upgraded sandbox with ports mapped...")
    new_id = f"sandbox-default-upgraded"
    orch._ensure_network()
    
    new_container = client.containers.run(
        image="rip-sandbox-backup:latest", 
        name=new_id, 
        detach=True, 
        network=orch.SANDBOX_NETWORK,
        ports={f"{orch.STREAM_AGENT_PORT}/tcp": ("127.0.0.1", None)},
        labels={
            orch.SANDBOX_LABEL: "true", 
            "project_id": "default", 
            "user_id": "api-key:4", 
            "environment": "python", 
            "created_at": datetime.datetime.now(datetime.UTC).isoformat()
        },
        mem_limit="2g", nano_cpus=2_000_000_000, memswap_limit="3g",
        environment={"PROJECT_ID": "default", "USER_ID": "api-key:4", "RIP_SANDBOX": "true"},
        working_dir="/workspace", tty=True, stdin_open=True,
    )
    new_container.reload()
    
    try:
        orch._deploy_stream_agent(new_container)
    except Exception as e:
        print("Warning: stream agent deploy failed:", e)

    await orch.update_sandbox_metadata(new_id, name="Aider / Codex Sandbox", description="Upgraded with persistent terminal support!")
    print(f"SUCCESS! New sandbox created: {new_id}")

if __name__ == "__main__":
    asyncio.run(main())
