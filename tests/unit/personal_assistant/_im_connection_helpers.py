"""Shared test doubles for IM connection unit tests."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig
from personal_assistant.reporter.upstream_reporter import UpstreamReporter, build_runtime_capabilities


class _FakeWebSocket:
    def __init__(self, incoming: list[str] | None = None) -> None:
        self.incoming = list(incoming or [])
        self.sent: list[str] = []
        self.closed = 0

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def recv(self) -> str:
        if not self.incoming:
            raise RuntimeError("socket closed")
        return self.incoming.pop(0)

    async def close(self) -> None:
        self.closed += 1


class _FailOnNthSendWebSocket(_FakeWebSocket):
    def __init__(self, *, fail_on_send_number: int, incoming: list[str] | None = None) -> None:
        super().__init__(incoming=incoming)
        self._fail_on_send_number = fail_on_send_number
        self._send_count = 0

    async def send(self, data: str) -> None:
        self._send_count += 1
        if self._send_count == self._fail_on_send_number:
            raise RuntimeError("socket closed")
        await super().send(data)


def _agents(tmp_path: Path) -> tuple[AgentWorkspaceConfig, ...]:
    workspace = tmp_path / "agent-a"
    workspace.mkdir()
    return (
        AgentWorkspaceConfig(
            agent_id="agent-a",
            workspace_root=workspace,
            title="Agent A",
            skills=("plan", "playwright"),
            tool_allowlist=("read", "bash"),
            default_model="codex_oauth:gpt-5.5",
        ),
    )


def _write_skill(root: Path, dir_name: str, *, frontmatter_name: str | None = None) -> None:
    skill_dir = root / dir_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    declared_name = frontmatter_name or dir_name
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {declared_name}\ndescription: {declared_name} skill\n---\n",
        encoding="utf-8",
    )


def _minimal_reporter(tmp_path: Path) -> UpstreamReporter:
    workspace = tmp_path / "agent-a"
    workspace.mkdir(exist_ok=True)
    agents = (
        AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),
    )
    return UpstreamReporter(
        node=NodeConfig(node_id="n1"),
        agents=agents,
        send_frame=lambda _mt, _p: None,
        capabilities=build_runtime_capabilities(),
    )


async def _connect_fake(
    socket: _FakeWebSocket,
    connect_calls: list[tuple[str, dict[str, str]]],
    url: str,
    headers: dict[str, str],
) -> _FakeWebSocket:
    connect_calls.append((url, headers))
    return socket
