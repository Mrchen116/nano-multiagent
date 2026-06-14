"""Shared test doubles for IM connection unit tests."""

from __future__ import annotations

from pathlib import Path

from personal_assistant.config.local_store import AgentWorkspaceConfig, NodeConfig
from personal_assistant.reporter.upstream_reporter import (
    UpstreamReporter,
    build_runtime_capabilities,
)


def _build_test_kernel(repo_root: Path):
    """Build a real PA Kernel for capability-reporting tests (refactor-406-M2).

    The reporter now projects from ``kernel.list_*`` (决策 4), so capability tests
    need a live kernel. Uses the conftest test LLM payload and the PA factory so the
    kernel carries the same skill_search_roots a production PA gateway has.
    """
    import tests.conftest as _conftest  # noqa: PLC0415
    from agent.sdk import LLMConfig  # noqa: PLC0415
    from personal_assistant.product import build_pa_kernel  # noqa: PLC0415

    llm = LLMConfig.from_payload(_conftest._DEFAULT_TEST_PAYLOAD)
    return build_pa_kernel(llm=llm, cron_services={}, repo_root=repo_root)


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
    def __init__(
        self, *, fail_on_send_number: int, incoming: list[str] | None = None
    ) -> None:
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


def _write_skill(
    root: Path, dir_name: str, *, frontmatter_name: str | None = None
) -> None:
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
    agents = (AgentWorkspaceConfig(agent_id="agent-a", workspace_root=workspace),)
    kernel = _build_test_kernel(tmp_path / "kernel-root")
    return UpstreamReporter(
        node=NodeConfig(node_id="n1"),
        agents=agents,
        send_frame=lambda _mt, _p: None,
        capabilities=build_runtime_capabilities(kernel),
    )


async def _connect_fake(
    socket: _FakeWebSocket,
    connect_calls: list[tuple[str, dict[str, str]]],
    url: str,
    headers: dict[str, str],
) -> _FakeWebSocket:
    connect_calls.append((url, headers))
    return socket
