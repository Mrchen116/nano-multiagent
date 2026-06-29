"""IM 黑盒客户端 — 把测试当成一个真实 IM 用户，只走对外 HTTP + WebSocket 接口。

design.md 决策 2:11 条关键路径都需要这一层，集中后单条测试只写「旅程脚本 + 鲁棒断言」。
客户端**不 import 任何产品代码**——它通过 IM 的公开 HTTP/WS 契约观察被测系统，
等价于真实前端所触达的那一面。

WS 事件流（``EventFrame`` / ``IMUserWebSocket`` / ``mention_tag`` / 窗口常量）拆在
``_im_ws``；「轮询直到条件成立」的共享 helper 在 ``_im_polling``（单文件 ≤400 行 + 消重）。
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from ._im_gateway import restart_gateway
from ._im_polling import poll_until
from ._im_ws import (
    DEFAULT_EVENT_TIMEOUT,
    IMUserWebSocket,
    mention_tag,
)
from ._im_ws import (
    ws_connect as _ws_connect,
)

# 向后兼容 re-export:历史调用点从 ``_im_client`` 取这些符号(测试文件 import 处)。
__all__ = [
    "DEFAULT_EVENT_TIMEOUT",
    "IMClient",
    "IMUserWebSocket",
    "mention_tag",
    "restart_gateway",
]


class IMClient:
    """对一台真 IM 实例的黑盒客户端:auth / 会话 / 消息 / WS / 权限 / 建 agent。"""

    # 类级追踪经 create_agent 建出的 agent_id(跨所有 client 实例共享):
    # 经 IM 动态建的 agent 其 workspace 实际落在主目录 ~/nano-assistant/workspace/<agent_id>
    # (产品隔离 gap,见 #127——且 IM 返回的 workspace_root 是 IM 侧映射路径,≠ gateway 实际
    # 落地的主目录路径,故按 agent_id 拼主目录路径清理才准),不在 e2e 隔离区 →
    # conftest session teardown 据此清理,避免污染主仓。
    created_agent_ids: list[str] = []

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
        nodes = poll_until(
            self.list_nodes,
            lambda ns: any(n.get("status") == "online" for n in ns),
            timeout=timeout,
            desc="online node",
        )
        return next(n["node_id"] for n in nodes if n.get("status") == "online")

    def list_agents(self) -> list[dict[str, Any]]:
        resp = self._http.get("/im/v1/agents", headers=self._auth_headers)
        resp.raise_for_status()
        return resp.json()

    def first_agent_id(self) -> str:
        """返回任一已注册 agent 的 agent_id(用于直聊奠基用例)。"""
        agents = self.list_agents()
        assert agents, "no agents registered on the node"
        return agents[0]["agent_id"]

    def wait_for_agent_listed(self, agent_id: str, *, timeout: float = 40.0) -> None:
        """轮询 ``GET /agents`` 直到 ``agent_id`` 出现(新建 agent 落地上线信号)。"""
        poll_until(
            lambda: [a["agent_id"] for a in self.list_agents()],
            lambda ids: agent_id in ids,
            timeout=timeout,
            interval=1.0,
            desc=f"agent {agent_id!r} listed",
        )

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
        created = resp.json()
        # 记下 agent_id 供 session teardown 按主目录路径清理(主目录残留,见 #127)。
        IMClient.created_agent_ids.append(agent_id)
        return created

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

    def fork_conversation(self, conversation_id: str, fork_message_id: str) -> str:
        """从一条已完成 agent 回复 fork 出分支单聊(feat-445)，返回新 conversation_id。"""
        resp = self._http.post(
            f"/im/v1/conversations/{conversation_id}/fork",
            headers=self._auth_headers,
            json={"fork_message_id": fork_message_id},
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def agent_messages(self, conversation_id: str, agent_id: str) -> list[dict]:
        """该会话里由 ``agent_id`` 发出的消息(按 REST 历史 sender.id 区分)。

        ``message.completed`` WS 帧不带 sender,REST item 的 ``sender`` ActorPayload 才是
        黑盒区分「哪个 agent 发的」的稳锚(群聊双 agent 场景必需)。
        """
        out = []
        for msg in self.list_messages(conversation_id):
            sender = msg.get("sender") or {}
            if sender.get("type") == "agent" and sender.get("id") == agent_id:
                out.append(msg)
        return out

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

        def _hit(msgs: list[dict]) -> dict | None:
            for msg in msgs:
                if msg.get("sender_type") == "agent" and sentinel in (
                    msg.get("content") or ""
                ):
                    return msg
            return None

        result = poll_until(
            lambda: _hit(self.list_messages(conversation_id)),
            lambda m: m is not None,
            timeout=timeout,
            interval=1.0,
            desc=f"agent reply containing {sentinel!r}",
        )
        assert result is not None
        return result

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
        ws = _ws_connect(f"{ws_url}/im/ws/user?token={self.token}")
        ws.send(json.dumps({"op": "resume", "after_event_id": after_event_id}))
        return IMUserWebSocket(ws)

    def close(self) -> None:
        self._http.close()
