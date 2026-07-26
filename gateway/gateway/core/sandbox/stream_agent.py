#!/usr/bin/env python3
"""
stream_agent.py — runs INSIDE the sandbox container, once, in the background.

Listens on a plain TCP port (published by Docker at container-creation
time, e.g. `ports={"7000/tcp": ("127.0.0.1", None)}`). For each incoming
JSON command request, it forks a real pty, execs the command attached to
that pty, and streams raw output back over the TCP connection as it is
produced.

WHY THIS FIXES THE WINDOWS BUFFERING PROBLEM
---------------------------------------------
- The pty is allocated by THIS process (pty.fork), so the child's stdout
  is a real pseudo-terminal. glibc/CPython treat a tty as line-buffered,
  so the child writes output as soon as a line (or partial chunk) exists
  — there is no "wait for EOF" happening inside the container.
- Output is forwarded over an ordinary published TCP socket, NOT through
  Docker's exec/attach streaming machinery. On Docker Desktop for Windows,
  regular port publishing is plain, reliable port-forwarding; it is
  specifically the exec-attach HTTP/npipe streaming path that has been
  observed to buffer everything until the process exits. Avoiding that
  path is the actual fix — nothing about Python buffering needs to change.

No third-party packages required — pty, asyncio, json, os are stdlib and
already present in python:3.12-slim.
"""
import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import sys
import termios

HOST = "0.0.0.0"  # binds inside the container's own network namespace
PORT = int(os.environ.get("STREAM_AGENT_PORT", "7000"))
END_MARKER = b"\x00__CMD_DONE__\x00"


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    pid, master_fd = pty.fork()

    if pid == 0:
        # ---- child process ----
        # Start bash as a login shell so it sources profiles
        os.execvp("/bin/bash", ["/bin/bash", "-l"])
        os._exit(127)

    # ---- parent process: give the pty a real size ----
    try:
        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass

    os.set_blocking(master_fd, False)
    loop = asyncio.get_event_loop()

    # Forward output from PTY to TCP
    async def forward_pty_to_writer():
        def _read_chunk() -> bytes:
            try:
                return os.read(master_fd, 4096)
            except OSError:
                return b""

        while True:
            chunk = await loop.run_in_executor(None, _read_chunk)
            if chunk:
                writer.write(chunk)
                await writer.drain()
            else:
                wpid, status = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    break
                await asyncio.sleep(0.01)
        writer.close()

    output_task = asyncio.create_task(forward_pty_to_writer())

    # Read from TCP and write to PTY
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            req = json.loads(line.decode("utf-8", errors="replace"))
            command = req.get("command")
            input_text = req.get("input")

            if command is not None:
                # To know when the command finishes, we append an echo command.
                # Note: If the command is interactive, this echo will be in the input buffer
                # and might be consumed by the command if it reads from stdin.
                # However, for non-interactive commands this properly signals completion.
                # This is a limitation of a persistent PTY session compared to one-off execs.
                cmd_line = f"{command}\necho -ne '\\x00__CMD_DONE__\\x00{{\"exit_code\": $?}}\\n'\n"
                os.write(master_fd, cmd_line.encode())
            elif input_text is not None:
                os.write(master_fd, input_text.encode())
    except Exception as e:
        try:
            writer.write(END_MARKER + json.dumps({"exit_code": -1, "error": str(e)}).encode() + b"\n")
            await writer.drain()
        except Exception:
            pass
    finally:
        writer.close()
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        output_task.cancel()





async def main() -> None:
    server = await asyncio.start_server(handle_client, HOST, PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    asyncio.run(main())
