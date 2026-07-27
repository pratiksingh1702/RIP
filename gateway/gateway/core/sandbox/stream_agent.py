#!/usr/bin/env python3
"""stream_agent.py — persistent PTY session with RIP prompt markers."""
import asyncio
import fcntl
import json
import os
import pty
import signal
import struct
import sys
import termios

HOST = "0.0.0.0"
PORT = int(os.environ.get("STREAM_AGENT_PORT", "7000"))


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    pid, master_fd = pty.fork()

    if pid == 0:
        os.environ["PS1"] = "\n__RIP_PROMPT__\n"
        os.environ["PROMPT_COMMAND"] = ""
        os.environ["TERM"] = "dumb"
        os.execvp("/bin/bash", ["/bin/bash", "--norc", "--noprofile"])
        os._exit(127)

    try:
        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
    except OSError:
        pass

    os.set_blocking(master_fd, False)
    loop = asyncio.get_event_loop()

    async def forward_pty_to_writer():
        def _read_chunk():
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

    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            req = json.loads(line.decode("utf-8", errors="replace"))
            command = req.get("command")
            input_text = req.get("input")

            if command is not None:
                os.write(master_fd, f"{command}\n".encode())
            elif input_text is not None:
                os.write(master_fd, input_text.encode())
    except Exception:
        pass
    finally:
        writer.close()
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        output_task.cancel()


async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    asyncio.run(main())
