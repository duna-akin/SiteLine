import asyncio
import json
import sys
import types

import pytest

from siteline.demo import demo_bytes
from siteline.docx_redline import parse_docx
from siteline.sandbox import SandboxError, parse_in_daytona


class FakeDaytonaError(Exception):
    pass


class FakeSandbox:
    id = "sbx-test"

    def __init__(self, exit_code: int):
        self.files: dict[str, bytes] = {}
        self.deleted = False
        self.fs = types.SimpleNamespace(upload_file=self._upload)
        self.process = types.SimpleNamespace(exec=self._exec)
        self.exit_code = exit_code

    async def _upload(self, data: bytes, path: str) -> None:
        self.files[path] = data

    async def _exec(self, cmd: str, timeout: int):
        result = json.dumps(parse_docx(self.files["/tmp/siteline/input.docx"])) if self.exit_code == 0 else "boom"
        return types.SimpleNamespace(exit_code=self.exit_code, result=result)

    async def delete(self) -> None:
        self.deleted = True


@pytest.fixture
def fake_daytona(monkeypatch):
    """Stands in for the daytona SDK; returns the sandbox the next create() hands out."""
    holder: dict[str, FakeSandbox] = {}

    class AsyncDaytona:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def create(self, params, timeout):
            assert params["network_block_all"] is True
            return holder["sandbox"]

    module = types.ModuleType("daytona")
    module.AsyncDaytona = AsyncDaytona
    module.CreateSandboxFromSnapshotParams = dict
    module.DaytonaError = FakeDaytonaError
    monkeypatch.setitem(sys.modules, "daytona", module)
    return holder


def run(data: bytes):
    phases: list[tuple[str, str, float | None, str]] = []
    result = asyncio.run(parse_in_daytona(data, lambda _: None, phase=lambda *p: phases.append(p)))
    return result, phases


def test_sandbox_reports_each_phase_with_its_time(fake_daytona):
    fake_daytona["sandbox"] = FakeSandbox(exit_code=0)
    (parsed, sandbox_id), phases = run(demo_bytes())

    assert sandbox_id == "sbx-test" and len(parsed["changes"]) == 14
    assert [(name, state) for name, state, _, _ in phases] == [
        ("create", "active"), ("create", "done"),
        ("upload", "active"), ("upload", "done"),
        ("parse", "active"), ("parse", "done"),
        ("output", "active"), ("output", "done"),
        ("delete", "active"), ("delete", "done"),
    ]
    done = {name: (seconds, detail) for name, state, seconds, detail in phases if state == "done"}
    assert all(seconds is not None and seconds >= 0 for seconds, _ in done.values())
    assert done["create"][1] == "sbx-test"
    assert done["output"][1].endswith("KB JSON")
    assert fake_daytona["sandbox"].deleted


def test_failed_parse_is_reported_and_the_sandbox_still_deleted(fake_daytona):
    fake_daytona["sandbox"] = FakeSandbox(exit_code=1)
    phases: list[tuple] = []
    with pytest.raises(SandboxError):
        asyncio.run(parse_in_daytona(demo_bytes(), lambda _: None, phase=lambda *p: phases.append(p)))

    states = [(name, state) for name, state, _, _ in phases]
    assert ("parse", "failed") in states and ("output", "active") not in states
    assert states[-1] == ("delete", "done") and fake_daytona["sandbox"].deleted
