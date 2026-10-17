"""Parse a Word file in a fresh Daytona sandbox; only JSON comes back, then the sandbox is deleted.

The sandbox has no network access and runs the same stdlib parser as the local fallback.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

from siteline.docx_redline import parse_docx

PARSER_PATH = Path(__file__).with_name("docx_redline.py")
REMOTE_DIR = "/tmp/siteline"

Log = Callable[[str], None]


class SandboxError(Exception):
    pass


def parse_local(data: bytes) -> dict:
    return parse_docx(data)


async def parse_in_daytona(data: bytes, log: Log, label: str = "upload") -> tuple[dict, str]:
    """Returns (parsed JSON, sandbox id). Raises SandboxError on failure."""
    from daytona import AsyncDaytona, CreateSandboxFromSnapshotParams, DaytonaError

    started = time.perf_counter()
    async with AsyncDaytona() as daytona:
        try:
            sandbox = await daytona.create(
                CreateSandboxFromSnapshotParams(
                    language="python",
                    network_block_all=True,
                    labels={"app": "siteline", "job": label},
                    ttl_minutes=15,
                    ephemeral=True,
                ),
                timeout=90,
            )
        except DaytonaError as e:
            raise SandboxError(f"Daytona could not create a sandbox: {e}") from e
        log(f"sandbox {sandbox.id} started in {time.perf_counter() - started:.1f} s (network blocked)")
        try:
            await sandbox.fs.upload_file(PARSER_PATH.read_bytes(), f"{REMOTE_DIR}/docx_redline.py")
            await sandbox.fs.upload_file(data, f"{REMOTE_DIR}/input.docx")
            log(f"uploaded input.docx ({len(data) // 1024} KB) and parser")
            resp = await sandbox.process.exec(
                f"python3 {REMOTE_DIR}/docx_redline.py {REMOTE_DIR}/input.docx", timeout=60
            )
            if resp.exit_code != 0:
                raise SandboxError(f"Parser exited with {resp.exit_code}: {resp.result[:300]}")
            try:
                parsed = json.loads(resp.result)
            except json.JSONDecodeError as e:
                raise SandboxError("Sandbox returned output that is not JSON") from e
            if "error" in parsed:
                raise SandboxError(parsed["error"])
            log(f"parser returned JSON ({len(resp.result) // 1024} KB, {len(parsed['changes'])} changes)")
            return parsed, sandbox.id
        except DaytonaError as e:
            raise SandboxError(f"Daytona error: {e}") from e
        finally:
            try:
                await sandbox.delete()
                log(f"sandbox {sandbox.id} deleted")
            except DaytonaError as e:
                log(f"sandbox {sandbox.id} delete failed ({e}); TTL removes it within 15 min")
