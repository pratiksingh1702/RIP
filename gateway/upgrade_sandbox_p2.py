import sys, asyncio, datetime
sys.path.insert(0, r"C:\Users\Dell\Downloads\RIP\gateway")
from gateway.core.sandbox.orchestrator import SandboxOrchestrator

async def main():
    orch = SandboxOrchestrator()
    sandbox_id = "sandbox-default-c07290e6"
    client = orch.client
    
    print("2. Stopping and renaming old sandbox...")
    container = client.containers.get(sandbox_id)
    try:
        container.stop()
    except Exception as e:
        print("Stop error (ignoring):", e)
    container.rename(sandbox_id + "-old")
    
    print("3. Creating upgraded sandbox with ports mapped...")
    # Keep the SAME sandbox ID so the Flutter app knows about it, or let the app discover the new one?
    # If we use the exact SAME sandbox_id, the app won't even notice it changed except for being more responsive!
    new_id = sandbox_id
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
    print(f"SUCCESS! Sandbox upgraded and port exposed: {new_id}")

if __name__ == "__main__":
    asyncio.run(main())
