"""IM 黑盒客户端 — 把测试当成一个真实 IM 用户，只走对外 HTTP + WebSocket 接口。

design.md 决策 2:11 条关键路径都需要这一层，集中后单条测试只写「旅程脚本 + 鲁棒断言」。
客户端**不 import 任何产品代码**——它通过 IM 的公开 HTTP/WS 契约观察被测系统，
等价于真实前端所触达的那一面。

WebSocket 依赖（``websockets``）在模块顶层 ``pytest.importorskip``：缺失则整组 e2e 干净
skip 而非 ImportError 崩溃（design.md 决策 2 风险项）。
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx
import pytest

# 决策 2 风险缓解:WS 客户端依赖可选化。缺失 → 整组 skip,不崩。
websockets = pytest.importorskip(
    "websockets",
    reason="websockets is required for IM WebSocket critical-path e2e",
)
from websockets.sync.client import connect as ws_connect  # noqa: E402


# 真 LLM + 真进程时序下事件到达偏慢;窗口集中成常量便于按需放宽(决策 4)。
DEFAULT_EVENT_TIMEOUT = 90.0
# 否定式断言(B 不抢话 / deny 后工具不执行)的「足够宽等待窗」(决策 4)。
NEGATIVE_ASSERT_WINDOW = 25.0


def mention_tag(agent_id: str) -> str:
    """拼一个 IM wire 层唯一认得的 agent mention 标签。

    relay_service.py 只认 ``<mention type="agent" target_id="X"/>``,不认 ``@文本``。
    """
    return f'<mention type="agent" target_id="{agent_id}"/>'


@dataclass
class EventFrame:
    """一帧用户流 WebSocket 事件(``{op:"event", ...}``)的轻封装。"""

    event_type: str
    event_id: int
    conversation_id: str | None
    data: dict[str, Any]

    @classmethod
    def from_wire(cls, raw: dict[str, Any]) -> "EventFrame":
        return cls(
            event_type=raw.get("event_type", ""),
            event_id=int(raw.get("event_id", 0)),
            conversation_id=raw.get("conversation_id"),
            data=raw.get("data") or {},
        )


class IMUserWebSocket:
    """一条已完成 ``resume`` 握手的用户流 WebSocket，带有界轮询的事件等待。"""

    def __init__(self, ws: Any) -> None:
        self._ws = ws
        # resume 回放或乱序到达的事件先缓冲,wait_for_event 先扫缓冲再读新帧。
        self._buffer: list[EventFrame] = []

    def _drain_one(self, timeout: float) -> EventFrame | None:
        """读一帧;非 ``event`` 帧(如 ``resync_required``)跳过。超时返回 None。"""
        try:
            raw_text = self._ws.recv(timeout=timeout)
        except TimeoutError:
            return None
        try:
            raw = json.loads(raw_text)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(raw, dict) or raw.get("op") != "event":
            return None
        return EventFrame.from_wire(raw)

    def wait_for_event(
        self,
        event_type: str,
        predicate: Callable[[EventFrame], bool] | None = None,
        *,
        timeout: float = DEFAULT_EVENT_TIMEOUT,
    ) -> EventFrame:
        """等待第一帧 ``event_type`` 且满足 ``predicate`` 的事件;超时 raise AssertionError。

        先扫已缓冲帧,再有界轮询新帧;不匹配的事件回收进缓冲供后续 wait 复用。
        """
        deadline = time.monotonic() + timeout

        # 1) 先扫缓冲。
        for i, frame in enumerate(self._buffer):
            if frame.event_type == event_type and (
                predicate is None or predicate(frame)
            ):
                del self._buffer[i]
                return frame

        # 2) 有界轮询新帧。
        while time.monotonic() < deadline:
            frame = self._drain_one(timeout=max(0.1, deadline - time.monotonic()))
            if frame is None:
                continue
            if frame.event_type == event_type and (
                predicate is None or predicate(frame)
            ):
                return frame
            # 不匹配但可能后面要用 → 缓冲。
            self._buffer.append(frame)

        raise AssertionError(
            f"timed out after {timeout}s waiting for event_type={event_type!r}; "
            f"buffered events so far: "
            f"{[(f.event_type, f.event_id) for f in self._buffer]}"
        )

    def assert_no_event(
        self,
        predicate: Callable[[EventFrame], bool],
        *,
        window: float = NEGATIVE_ASSERT_WINDOW,
    ) -> None:
        """否定式断言:在 ``window`` 秒内没有任何满足 ``predicate`` 的事件出现。

        决策 4:否定断言天生偏脆,靠「足够宽窗口 + 只断协议事件缺席」缓解。
        """
        deadline = time.monotonic() + window
        # 先查已缓冲帧。
        for frame in self._buffer:
            if predicate(frame):
                raise AssertionError(
                    f"unexpected event already buffered: "
                    f"type={frame.event_type} data_keys={list(frame.data)}"
                )
        while time.monotonic() < deadline:
            frame = self._drain_one(timeout=max(0.1, deadline - time.monotonic()))
            if frame is None:
                continue
            self._buffer.append(frame)
            if predicate(frame):
                raise AssertionError(
                    f"unexpected event within {window}s window: "
                    f"type={frame.event_type} data_keys={list(frame.data)}"
                )

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:  # noqa: BLE001 — teardown best-effort
            pass


class IMClient:
    """对一台真 IM 实例的黑盒客户端:auth / 会话 / 消息 / WS / 权限 / 建 agent。"""

    def __init__(self, im_url: str, *, http_timeout: float = 30.0) -> None:
        self.im_url = im_url.rstrip("/")
        self._http = httpx.Client(base_url=self.im_url, timeout=http_timeout)
        self.token: str | None = None
        self.user_id: str | None = None
        # owner_id 是建 agent 的归属键:IM 的 runtime-selectable 列表按 owner 过滤
        # (repositories.list_runtime_selectable_profiles_for_owner),建 agent 不带它
        # → profile.owner_id 落空串 → 绑定节点上的新 agent 被过滤掉、永不出现在 /agents。
        self.owner_id: str | None = None

    # ── auth ──────────────────────────────────────────────────────────────

    def register_or_login(
        self, username: str, password: str, *, display_name: str | None = None
    ) -> str:
        """注册(若不存在)并登录,返回 access_token;副作用:缓存 token + user_id。"""
        self._http.post(
            "/im/v1/auth/register",
            json={
                "username": username,
                "password": password,
                "display_name": display_name or username,
            },
        )  # 409 already-exists 视为正常,走 login 拿 token。
        resp = self._http.post(
            "/im/v1/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        body = resp.json()
        self.token = body["access_token"]
        self.user_id = body["user"]["id"]
        self.owner_id = body["user"]["owner_id"]
        return self.token

    @property
    def _auth_headers(self) -> dict[str, str]:
        assert self.token is not None, "call register_or_login() first"
        return {"Authorization": f"Bearer {self.token}"}

    # ── nodes / agents ────────────────────────────────────────────────────

    def list_nodes(self) -> list[dict[str, Any]]:
        resp = self._http.get("/im/v1/nodes", headers=self._auth_headers)
        resp.raise_for_status()
        return resp.json()

    def wait_for_online_node(self, *, timeout: float = 30.0) -> str:
        """轮询 ``GET /nodes`` 直到出现一个 online 节点,返回其 node_id。"""
        deadline = time.monotonic() + timeout
        last: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            last = self.list_nodes()
            for node in last:
                if node.get("status") == "online":
                    return node["node_id"]
            time.sleep(0.5)
        raise AssertionError(
            f"no online node within {timeout}s; last nodes snapshot: {last}"
        )

    def list_agents(self) -> list[dict[str, Any]]:
        resp = self._http.get("/im/v1/agents", headers=self._auth_headers)
        resp.raise_for_status()
        return resp.json()

    def first_agent_id(self) -> str:
        """返回任一已注册 agent 的 agent_id(用于直聊奠基用例)。"""
        agents = self.list_agents()
        assert agents, "no agents registered on the node"
        return agents[0]["agent_id"]

    def get_agent_config(self, agent_id: str) -> dict[str, Any]:
        """读一个 agent 的完整配置(含 profile_version,供乐观锁 PATCH 用)。"""
        resp = self._http.get(
            f"/im/v1/agents/{agent_id}/config", headers=self._auth_headers
        )
        resp.raise_for_status()
        return resp.json()

    def update_agent_config(self, agent_id: str, **changes: Any) -> dict[str, Any]:
        """改一个 agent 的配置(PATCH 全量 + 乐观锁)。

        PATCH 端点是全量更新且要求 ``profile_version`` 乐观锁:先 GET 现配置,把 ``changes``
        覆盖上去再整体 PATCH。cron/heartbeat 路径靠它开 ``features['cron_scheduling']`` /
        ``features['heartbeat']`` + 注入 ``heartbeat_json`` 节律。
        """
        current = self.get_agent_config(agent_id)
        body: dict[str, Any] = {
            "profile_version": current["profile_version"],
            "display_name": current["display_name"],
            "description": current.get("description", ""),
            "system_prompt": current.get("system_prompt", ""),
            "skills": current.get("skills", []),
            "tool_allowlist": current.get("tool_allowlist", []),
            "group_reply_policy": current["group_reply_policy"],
            "default_model": current.get("default_model"),
            "features": dict(current.get("features") or {}),
            "custom_prompt": current.get("custom_prompt"),
        }
        # heartbeat_json 只在显式传入时放进 body:PATCH 的 model_validator 见到
        # heartbeat_json=None 键存在时,会把 heartbeat dict 形式 pop 掉、不转换
        # (validator 条件 `"heartbeat_json" not in data`),故不预填 None 占位。
        existing_hb = current.get("heartbeat_json")
        if existing_hb is not None and "heartbeat_json" not in changes:
            body["heartbeat_json"] = existing_hb
        # changes 里 features 做合并(不整段覆盖),其余字段直接替换。
        if "features" in changes:
            body["features"].update(changes.pop("features"))
        body.update(changes)
        resp = self._http.patch(
            f"/im/v1/agents/{agent_id}/config",
            headers=self._auth_headers,
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    def create_agent(
        self,
        node_id: str,
        agent_id: str,
        *,
        display_name: str | None = None,
        system_prompt: str = "",
        group_reply_policy: str = "MENTION",
        tool_allowlist: list[str] | None = None,
        skills: list[str] | None = None,
        default_model: str | None = None,
    ) -> dict[str, Any]:
        """经 IM 配置中心在指定节点新建一个 agent(POST /nodes/{id}/agents)。

        必带 ``owner_id``(默认取登录缓存的 owner):IM 的 /agents 列表按 owner 过滤,
        漏传则新 agent 落 ownerless 而绑定节点已归属本 owner → 被过滤、永不可见可聊。
        """
        assert self.owner_id is not None, "call register_or_login() first"
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "owner_id": self.owner_id,
            "display_name": display_name or agent_id,
            "system_prompt": system_prompt,
            "group_reply_policy": group_reply_policy,
            "tool_allowlist": tool_allowlist or [],
            "skills": skills or [],
        }
        if default_model is not None:
            payload["default_model"] = default_model
        resp = self._http.post(
            f"/im/v1/nodes/{node_id}/agents",
            headers=self._auth_headers,
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    # ── conversations ─────────────────────────────────────────────────────

    def create_direct_conversation(
        self, agent_id: str, *, title: str | None = None
    ) -> str:
        """建一个「用户 + 单个 agent」直聊会话,返回 conversation_id。

        participants 必须含用户自己 + 目标 agent(IM 不会隐式补 caller)。
        """
        return self._create_conversation(
            title=title or f"direct-{agent_id}",
            agent_ids=[agent_id],
        )

    def create_group_conversation(
        self, agent_ids: list[str], *, title: str | None = None
    ) -> str:
        """建一个「用户 + 多个 agent」群会话,返回 conversation_id。"""
        return self._create_conversation(
            title=title or "group-" + "-".join(agent_ids),
            agent_ids=agent_ids,
        )

    def _create_conversation(self, *, title: str, agent_ids: list[str]) -> str:
        assert self.user_id is not None, "call register_or_login() first"
        participants = [{"type": "user", "id": self.user_id}]
        participants += [{"type": "agent", "id": aid} for aid in agent_ids]
        resp = self._http.post(
            "/im/v1/conversations",
            headers=self._auth_headers,
            json={"title": title, "participants": participants},
        )
        resp.raise_for_status()
        return resp.json()["id"]

    # ── messages ──────────────────────────────────────────────────────────

    def send_message(
        self,
        conversation_id: str,
        content: str,
        *,
        mentions: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> str:
        """以用户身份发一条消息,返回 message_id。

        ``mentions`` 中每个 agent_id 拼成 ``<mention .../>`` 标签前缀进 content
        (IM wire 层只认标签,不认 @文本)。
        """
        assert self.user_id is not None, "call register_or_login() first"
        body = content
        if mentions:
            prefix = " ".join(mention_tag(aid) for aid in mentions)
            body = f"{prefix} {content}"
        headers = dict(self._auth_headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        resp = self._http.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            headers=headers,
            json={
                "sender": {"type": "user", "id": self.user_id},
                "content": body,
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def list_messages(self, conversation_id: str, *, limit: int = 50) -> list[dict]:
        """按插入序列出会话消息(返回 ``items`` 列表)。"""
        resp = self._http.get(
            f"/im/v1/conversations/{conversation_id}/messages",
            headers=self._auth_headers,
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json()["items"]

    def wait_for_agent_reply_with(
        self,
        conversation_id: str,
        sentinel: str,
        *,
        timeout: float = DEFAULT_EVENT_TIMEOUT,
    ) -> dict:
        """轮询消息历史,直到出现一条 agent 消息其 content 含 ``sentinel``。

        REST 兜底路径:某些场景(后台通知 / cron / heartbeat)的最终态在历史里更稳。
        """
        deadline = time.monotonic() + timeout
        last: list[dict] = []
        while time.monotonic() < deadline:
            last = self.list_messages(conversation_id)
            for msg in last:
                if msg.get("sender_type") == "agent" and sentinel in (
                    msg.get("content") or ""
                ):
                    return msg
            time.sleep(1.0)
        raise AssertionError(
            f"no agent reply containing sentinel {sentinel!r} within {timeout}s; "
            f"last messages: {[(m.get('sender_type'), m.get('content', '')[:60]) for m in last]}"
        )

    # ── permission ────────────────────────────────────────────────────────

    def resolve_permission(
        self,
        conversation_id: str,
        request_id: str,
        message_id: str,
        decision: str,
    ) -> dict:
        """提交一个权限审批决定(``allow_once`` / ``deny`` 等,值由 gateway 定义)。"""
        resp = self._http.post(
            f"/im/v1/conversations/{conversation_id}/permissions/{request_id}",
            headers=self._auth_headers,
            json={"message_id": message_id, "decision": decision},
        )
        resp.raise_for_status()
        return resp.json()

    # ── websocket ─────────────────────────────────────────────────────────

    def connect_ws(self, *, after_event_id: int = 0) -> IMUserWebSocket:
        """连用户流 WebSocket 并完成 ``resume`` 握手。

        ``after_event_id=0`` 表示只关心连接后新产生的事件(不回放历史)。
        """
        assert self.token is not None, "call register_or_login() first"
        ws_url = self.im_url.replace("http://", "ws://").replace("https://", "wss://")
        ws = ws_connect(f"{ws_url}/im/ws/user?token={self.token}")
        ws.send(json.dumps({"op": "resume", "after_event_id": after_event_id}))
        return IMUserWebSocket(ws)

    def close(self) -> None:
        self._http.close()


def restart_gateway(wt_dir: str, im_port: str) -> None:
    """重启 worktree 内的 Gateway 进程,复用同 config(保 node_id / workspace → 验续接)。

    e2e-up.sh 用 ``--foreground`` 起 Gateway(范式 B),pid 落在 ``$wt_dir/.gateway.pid``。
    先优雅杀,再用同一份 ``.gateway-config.yaml`` 重起 foreground,等就绪标志出现。
    """
    import os
    import signal

    pid_file = os.path.join(wt_dir, ".gateway.pid")
    cfg = os.path.join(wt_dir, ".gateway-config.yaml")
    log = os.path.join(wt_dir, ".gateway.log")

    # 1) 优雅杀旧进程。
    if os.path.exists(pid_file):
        with open(pid_file) as f:
            old_pid = int(f.read().strip())
        try:
            os.kill(old_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            try:
                os.kill(old_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.2)
        else:
            try:
                os.kill(old_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    # 2) 重起 foreground(复用同 config 同 node_id → 工作区/会话续接)。
    # repo_root 从本测试文件位置反推(tests/e2e/critical_paths → repo),
    # 不依赖 wt_dir 是 git 仓(它是 pytest tmp,非 checkout)。
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(repo_root, "src")
    log_handle = open(log, "a")
    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "personal_assistant.main",
            "--config",
            cfg,
            "--im-service-url",
            f"http://127.0.0.1:{im_port}",
            "--foreground",
            "--auto-bind",
        ],
        cwd=repo_root,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    # 3) 等就绪标志(沿用 e2e-up.sh 的探测口径)。
    ready_markers = (
        "auto-bound to IM",
        "Gateway started",
        "node_id=",
        "im_connection",
    )
    deadline = time.monotonic() + 40.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"gateway died during restart; see {log}")
        try:
            with open(log) as f:
                tail = f.read()
            if any(marker in tail for marker in ready_markers):
                return
        except FileNotFoundError:
            pass
        time.sleep(0.5)
    raise AssertionError(f"gateway did not signal readiness within 40s; see {log}")
