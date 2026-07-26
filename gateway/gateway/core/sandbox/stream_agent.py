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


async def run_command_pty(command: str, workdir: str, writer: asyncio.StreamWriter) -> None:
    """Fork a pty, exec `command` in it, and stream output back over `writer`."""
    pid, master_fd = pty.fork()

    if pid == 0:
        # ---- child process ----
        try:
            if workdir and os.path.isdir(workdir):
                os.chdir(workdir)
        except Exception:
            pass
        os.execvp("/bin/bash", ["/bin/bash", "-c", command])
        os._exit(127)  # only reached if execvp itself fails

    # ---- parent process: give the pty a real size ----
    # pty.fork() leaves winsize at 0x0, which some shells/kernels treat as
    # "already at line width", corrupting or dropping the first character
    # written on each line. Set a normal size immediately.
    try:
        winsize = struct.pack("HHHH", 24, 80, 0, 0)  # rows, cols, xpixel, ypixel
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass

    # ---- parent process: read the pty master and forward immediately ----
    loop = asyncio.get_event_loop()
    os.set_blocking(master_fd, False)
    status = None

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
            continue

        wpid, status = os.waitpid(pid, os.WNOHANG)
        if wpid == pid:
            break
        await asyncio.sleep(0.01)

    # Drain anything written between the last read and process exit
    try:
        while True:
            chunk = os.read(master_fd, 4096)
            if not chunk:
                break
            writer.write(chunk)
    except OSError:
        pass

    try:
        os.close(master_fd)
    except OSError:
        pass

    exit_code = os.waitstatus_to_exitcode(status) if status is not None else -1
    footer = json.dumps({"exit_code": exit_code}).encode()
    writer.write(END_MARKER + footer + b"\n")
    await writer.drain()


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        line = await reader.readline()
        if not line:
            return
        req = json.loads(line.decode("utf-8", errors="replace"))
        command = req.get("command", "")
        workdir = req.get("workdir", "/workspace")
        await run_command_pty(command, workdir, writer)
    except Exception as e:
        try:
            writer.write(END_MARKER + json.dumps({"exit_code": -1, "error": str(e)}).encode() + b"\n")
            await writer.drain()
        except Exception:
            pass
    finally:
        writer.close()


async def main() -> None:
    server = await asyncio.start_server(handle_client, HOST, PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    asyncio.run(main())
