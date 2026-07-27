"""关键路径:Agent 配置更新后既有聊天上下文连续(fake LLM,不烧真模型)。

incident #208 / bugfix-471:改 tools 等运行配置后,旧实现会删 binding 并开空 session,
页面历史还在但 Agent 实际上下文丢了。

旅程(真 IM + 真 Gateway 进程 + recording Anthropic stub):
1. 直聊发一句带哨兵 A 的消息,等到 agent 回复
2. PATCH agent ``tool_allowlist`` 增加 ``read``
3. 同一聊天再发带哨兵 B 的消息,等到回复
4. 断言 stub 记录的**最后一次** LLM 请求 messages 同时含 A 与 B
   (若回归成新空 session,最后一次只会有 B)

不依赖 ``:4000`` 真 proxy;断言点是上游请求体,对模型措辞不敏感。
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
import yaml

from ._im_client import IMClient
from .conftest import E2EStack, _dump_logs, _parse_ports_env

_REPO_ROOT = Path(__file__).resolve().parents[3]
_E2E_UP = _REPO_ROOT / "scripts" / "e2e-up.sh"
_E2E_DOWN = _REPO_ROOT / "scripts" / "e2e-down.sh"
_FREE_PORTS = _REPO_ROOT / "scripts" / "free-ports.sh"
_RECORDING_STUB = _REPO_ROOT / "scripts" / "fixtures" / "anthropic_sse_ok_recording.py"
_MAIN_CONFIG = Path.home() / ".nano-assistant" / "config.yaml"


@dataclass
class StubLLMStack(E2EStack):
    """带 recording stub 的真进程栈。"""

    record_path: str
    stub_port: int


def _message_blob(request: dict) -> str:
    """把 Anthropic /messages 请求里的可见文本拼成可搜索字符串。"""
    parts: list[str] = []
    for message in request.get("messages") or []:
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
            continue
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                elif isinstance(block, str):
                    parts.append(block)
    return "\n".join(parts)


def _tool_names(request: dict) -> set[str]:
    names: set[str] = set()
    for tool in request.get("tools") or []:
        if isinstance(tool, dict) and isinstance(tool.get("name"), str):
            names.add(tool["name"])
    return names


def _load_records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _wait_records(path: Path, minimum: int, *, timeout: float = 60.0) -> list[dict]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        records = _load_records(path)
        if len(records) >= minimum:
            return records
        time.sleep(0.2)
    records = _load_records(path)
    raise AssertionError(
        f"expected ≥{minimum} LLM requests within {timeout}s; got {len(records)}"
    )


def _rewrite_llm_to_stub(src: Path, dst: Path, stub_url: str) -> None:
    cfg = yaml.safe_load(src.read_text(encoding="utf-8"))
    llm = cfg.setdefault("llm", {})
    providers = llm.get("providers") or []
    if not providers:
        raise AssertionError(f"{src} has no llm.providers")
    for provider in providers:
        provider["base_url"] = stub_url
    # 去掉 thinking 附加体:stub 不需要,且部分模型附加项会改变请求形状。
    for provider in providers:
        for model in provider.get("models") or []:
            model.pop("extra_request_body", None)
    dst.write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


@pytest.fixture
def stub_llm_stack(tmp_path: Path) -> Iterator[StubLLMStack]:
    """起 recording Anthropic stub + 真 IM/Gateway;Gateway 的 llm 全指向 stub。"""
    if not _MAIN_CONFIG.exists():
        pytest.skip(
            f"main config not found: {_MAIN_CONFIG} — create it first (see "
            "docs/development/worktree-runtime.md)"
        )
    if not _RECORDING_STUB.exists():
        pytest.fail(f"missing fixture script: {_RECORDING_STUB}")

    stub_port = int(
        subprocess.check_output([str(_FREE_PORTS), "1"], text=True).split()[0]
    )
    record_path = tmp_path / "llm-requests.jsonl"
    stub_proc = subprocess.Popen(
        ["python3", str(_RECORDING_STUB), str(stub_port)],
        env={
            **os.environ,
            "NANO_FIXTURE_RECORD_PATH": str(record_path),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    # stub 就绪探活:端口可连即可(它只处理 POST)。
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if stub_proc.poll() is not None:
            err = stub_proc.stderr.read() if stub_proc.stderr else ""
            pytest.fail(f"recording stub exited early: {err}")
        try:
            with httpx.Client(timeout=0.3) as probe:
                # GET 会 501,但证明端口已 listen。
                probe.get(f"http://127.0.0.1:{stub_port}/")
            break
        except httpx.HTTPError:
            time.sleep(0.05)
    else:
        stub_proc.kill()
        pytest.fail("recording stub did not listen in time")

    main_for_up = tmp_path / "main-config-stubbed.yaml"
    _rewrite_llm_to_stub(_MAIN_CONFIG, main_for_up, f"http://127.0.0.1:{stub_port}")

    wt_dir = tmp_path / "stack"
    wt_dir.mkdir()
    up = subprocess.run(
        [
            "bash",
            str(_E2E_UP),
            "--wt",
            str(wt_dir),
            "--main-config",
            str(main_for_up),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            # e2e-up 里的 python 回退路径需要 PyYAML;确保用到仓库 venv。
            "PATH": f"{_REPO_ROOT / '.venv' / 'bin'}:{os.environ.get('PATH', '')}",
        },
    )
    if up.returncode != 0:
        stub_proc.kill()
        _dump_logs(wt_dir)
        pytest.fail(
            f"e2e-up.sh failed (rc={up.returncode}):\n"
            f"--- stdout ---\n{up.stdout}\n--- stderr ---\n{up.stderr}"
        )

    values = _parse_ports_env(wt_dir / ".e2e-ports.env")
    stack = StubLLMStack(
        im_url=values["IM_URL"],
        im_port=values["IM_PORT"],
        node_id=values.get("NODE_ID", ""),
        wt_dir=str(wt_dir),
        record_path=str(record_path),
        stub_port=stub_port,
    )
    try:
        yield stack
    finally:
        subprocess.run(
            ["bash", str(_E2E_DOWN), "--wt", str(wt_dir)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        stub_proc.terminate()
        try:
            stub_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            stub_proc.kill()
        home_ws_root = Path.home() / "nano-assistant" / "workspace"
        for agent_id in IMClient.created_agent_ids:
            ws_path = home_ws_root / agent_id
            if ws_path.parent == home_ws_root and ws_path.is_dir():
                shutil.rmtree(ws_path, ignore_errors=True)
        IMClient.created_agent_ids.clear()


@pytest.fixture
def stub_im_user(stub_llm_stack: StubLLMStack) -> Iterator[IMClient]:
    client = IMClient(stub_llm_stack.im_url)
    client.register_or_login("nano", "nano1234", display_name="Test User")
    yield client
    client.close()


@pytest.mark.e2e
def test_agent_config_update_keeps_chat_context_with_stub_llm(
    stub_im_user: IMClient, stub_llm_stack: StubLLMStack
) -> None:
    """先聊 → 改 tools → 再聊;最后一次 LLM 请求必须仍带上改配置前的用户句。"""
    agent_id = stub_im_user.first_agent_id()
    # 起点清空工具,确保后续 PATCH 真的改变 effective runtime。
    stub_im_user.update_agent_config(agent_id, tool_allowlist=[])
    conversation_id = stub_im_user.create_direct_conversation(agent_id)

    first = "CTXA" + secrets.token_hex(4).upper()
    second = "CTXB" + secrets.token_hex(4).upper()
    record = Path(stub_llm_stack.record_path)

    ws = stub_im_user.connect_ws()
    try:
        stub_im_user.send_message(
            conversation_id,
            f"请记住这个标记:{first}。先简短确认即可。",
        )
        ws.wait_for_event("message.completed")
        _wait_records(record, 1)

        stub_im_user.update_agent_config(agent_id, tool_allowlist=["read"])

        stub_im_user.send_message(
            conversation_id,
            f"继续刚才的对话。新标记是:{second}。",
        )
        ws.wait_for_event("message.completed")
        records = _wait_records(record, 2)
    finally:
        ws.close()

    last = records[-1]
    blob = _message_blob(last)
    assert first in blob, (
        "post-config-update LLM request lost earlier chat context; "
        f"missing {first!r} in last request messages. blob={blob!r}"
    )
    assert second in blob, (
        f"last LLM request missing the new user turn {second!r}; blob={blob!r}"
    )
    # 运行配置确实换了:最后一次请求应带上新增的 read 工具。
    assert "read" in _tool_names(last), (
        f"expected read tool after config update; tools={_tool_names(last)!r}"
    )
