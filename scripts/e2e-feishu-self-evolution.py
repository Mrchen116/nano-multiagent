#!/usr/bin/env python3
"""Run deterministic self-evolution receipts through a dedicated Feishu E2E Bot."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

from e2e_feishu_config import load_e2e_env

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURE = _ROOT / "scripts/fixtures/openai_self_evolution_recording.py"
_GATEWAY_ENTRYPOINT = _ROOT / "scripts/fixtures/e2e_gateway_verbose.py"
_NOTICE = "· background self-evolution review: skills updated"
_NOTICE_PREFIX = "· background self-evolution review:"
_RAW_MARKERS = (
    "Nothing to save.",
    "Save failed: controlled invalid memory target.",
    "Saved:",
)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _require_feishu_stack(worktree: Path) -> None:
    marker = worktree / ".e2e-ports.env"
    if not marker.is_file() or "export E2E_PROFILE=feishu" not in marker.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError("worktree must have an active --feishu E2E stack")


def _require_test_profile(
    status: dict[str, Any], values: dict[str, str], profile: str
) -> None:
    identities = status.get("identities")
    bot = identities.get("bot") if isinstance(identities, dict) else None
    if profile == "default" or status.get("verified") is not True:
        raise RuntimeError("dedicated non-default lark-cli profile is not verified")
    if status.get("appId") != values["NANO_MULTIAGENT_E2E_FEISHU_APP_ID"]:
        raise RuntimeError("dedicated lark-cli profile belongs to another App")
    if (
        not isinstance(bot, dict)
        or bot.get("verified") is not True
        or bot.get("openId") != values["NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID"]
    ):
        raise RuntimeError("dedicated lark-cli profile targets another Bot")


def _ports(worktree: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (worktree / ".e2e-ports.env").read_text(encoding="utf-8").splitlines():
        if line.startswith("export ") and "=" in line:
            key, value = line.removeprefix("export ").split("=", 1)
            values[key] = value
    return values


def _rewrite_llm_to_fixture(config_path: Path, fixture_url: str) -> None:
    """Point only the generated worktree config at the controlled OpenAI fixture."""

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    providers = payload["llm"]["providers"]
    for provider in providers:
        provider["name"] = "openai_compat"
        provider["base_url"] = fixture_url
        for model in provider.get("models") or []:
            model.pop("extra_request_body", None)
    config_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _start_fixture(worktree: Path) -> tuple[subprocess.Popen[str], str]:
    port = _free_port()
    record_path = worktree / ".feishu-self-evolution-llm.jsonl"
    process = subprocess.Popen(
        [sys.executable, str(_FIXTURE), str(port)],
        env={**os.environ, "NANO_FIXTURE_RECORD_PATH": str(record_path)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"controlled LLM exited early: {stderr}")
        try:
            httpx.get(f"{url}/state", timeout=0.3, trust_env=False).raise_for_status()
            return process, url
        except httpx.HTTPError:
            time.sleep(0.05)
    process.kill()
    process.wait(timeout=5)
    raise RuntimeError("controlled LLM did not become ready")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _has_reconnected(
    nodes: list[dict[str, Any]], *, node_id: str, started_after: str
) -> bool:
    return any(
        node.get("node_id") == node_id
        and node.get("status") == "online"
        and isinstance(node.get("last_heartbeat_at"), str)
        and node["last_heartbeat_at"] > started_after
        for node in nodes
    )


def _reset_session_bindings(worktree: Path) -> None:
    for suffix in ("", "-shm", "-wal"):
        (worktree / f"session_bindings.sqlite3{suffix}").unlink(missing_ok=True)


def _drop_session_bindings(worktree: Path) -> None:
    with sqlite3.connect(worktree / "session_bindings.sqlite3") as connection:
        connection.execute("DELETE FROM session_bindings")


def _restart_gateway(worktree: Path, fixture_url: str) -> None:
    pid_path = worktree / ".gateway.pid"
    old_pid = int(pid_path.read_text(encoding="utf-8").strip())
    os.kill(old_pid, signal.SIGTERM)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            os.kill(old_pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("original Gateway did not stop")

    # The old Gateway owns an immutable production-valued config snapshot and may
    # persist it while draining the probe run. Rewrite only after that writer exits,
    # so the replacement Kernel necessarily loads the controlled fixture route.
    _rewrite_llm_to_fixture(worktree / ".gateway-config.yaml", fixture_url)
    _reset_session_bindings(worktree)
    config = yaml.safe_load(
        (worktree / ".gateway-config.yaml").read_text(encoding="utf-8")
    )
    node_id = str(config["node"]["node_id"])
    im_url = _ports(worktree)["IM_URL"]
    started_after = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log = (worktree / ".gateway.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            str(_GATEWAY_ENTRYPOINT),
            "--config",
            str(worktree / ".gateway-config.yaml"),
            "--im-service-url",
            im_url,
            "--foreground",
            "--auto-bind",
        ],
        cwd=worktree,
        env={**os.environ, "PYTHONPATH": str(_ROOT / "src")},
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    log.close()
    pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
    with httpx.Client(base_url=im_url, timeout=5, trust_env=False) as client:
        response = client.post(
            "/im/v1/auth/login",
            json={"username": "nano", "password": "nano1234"},
        )
        response.raise_for_status()
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("replacement Gateway exited during startup")
            response = client.get("/im/v1/nodes", headers=headers)
            response.raise_for_status()
            worker_connected = "feishu worker status: state=connected" in (
                worktree / ".gateway.log"
            ).read_text(encoding="utf-8")
            if worker_connected and _has_reconnected(
                response.json(), node_id=node_id, started_after=started_after
            ):
                return
            time.sleep(0.2)
    raise RuntimeError("replacement Gateway did not become ready")


def _lark_json(profile: str, *args: str) -> dict[str, Any]:
    result = subprocess.run(
        ["lark-cli", "--profile", profile, *args, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
            "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
        },
    )
    if result.returncode != 0:
        raise RuntimeError("dedicated lark-cli profile command failed")
    payload = json.loads(result.stdout)
    if payload.get("ok") is not True:
        raise RuntimeError("dedicated lark-cli profile returned a failed envelope")
    return payload


def _send_lark(profile: str, bot_open_id: str, text: str) -> tuple[str, str]:
    payload = _lark_json(
        profile,
        "im",
        "+messages-send",
        "--as",
        "user",
        "--user-id",
        bot_open_id,
        "--text",
        text,
        "--idempotency-key",
        secrets.token_hex(12),
    )
    data = payload.get("data") or {}
    return str(data["chat_id"]), str(data["message_id"])


def _lark_messages(profile: str, chat_id: str) -> list[dict[str, Any]]:
    payload = _lark_json(
        profile,
        "im",
        "+chat-messages-list",
        "--as",
        "user",
        "--chat-id",
        chat_id,
        "--page-size",
        "50",
        "--no-reactions",
    )
    data = payload.get("data") or {}
    return [item for item in data.get("messages", []) if isinstance(item, dict)]


def _message_ids(messages: list[dict[str, Any]]) -> set[str]:
    return {
        str(message.get("message_id") or message.get("id"))
        for message in messages
        if isinstance(message.get("message_id") or message.get("id"), str)
    }


def _messages_after(
    messages: list[dict[str, Any]], prior_message_ids: set[str]
) -> list[dict[str, Any]]:
    return [
        message
        for message in messages
        if isinstance(message.get("message_id") or message.get("id"), str)
        and str(message.get("message_id") or message.get("id")) not in prior_message_ids
    ]


def _wait_lark_reply(
    profile: str,
    chat_id: str,
    prior_message_ids: set[str],
    marker: str,
    tag: str,
) -> list[dict[str, Any]]:
    return _wait(
        f"{tag} foreground reply",
        lambda: _lark_messages(profile, chat_id),
        lambda value: (
            marker in _texts(_messages_after(value, prior_message_ids))
            and tag in _texts(_messages_after(value, prior_message_ids))
        ),
    )


def _wait(label: str, read: Callable[[], Any], accept: Callable[[Any], bool]) -> Any:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        value = read()
        if accept(value):
            return value
        time.sleep(0.2)
    raise RuntimeError(f"timed out waiting for {label}")


def _texts(messages: list[dict[str, Any]]) -> str:
    return "\n".join(str(message.get("content") or "") for message in messages)


def _fixture_control(url: str, scenario: str, **extra: object) -> None:
    response = httpx.post(
        f"{url}/control",
        json={"scenario": scenario, **extra},
        timeout=5,
        trust_env=False,
    )
    response.raise_for_status()


def _fixture_event(url: str, event: str) -> None:
    _wait(
        event,
        lambda: httpx.get(f"{url}/state", timeout=5, trust_env=False).json(),
        lambda state: any(item.get("event") == event for item in state["events"]),
    )


class _IM:
    def __init__(self, url: str) -> None:
        self.client = httpx.Client(base_url=url, timeout=30, trust_env=False)
        response = self.client.post(
            "/im/v1/auth/login",
            json={"username": "nano", "password": "nano1234"},
        )
        response.raise_for_status()
        payload = response.json()
        self.headers = {"Authorization": f"Bearer {payload['access_token']}"}
        self.user_id = str(payload["user"]["id"])

    def bump_agent(self, marker: str, config_path: Path) -> None:
        current = self.client.get(
            "/im/v1/agents/e2e/config", headers=self.headers
        ).json()
        body = {
            "profile_version": current["profile_version"],
            "display_name": current["display_name"],
            "description": current.get("description", ""),
            "skills": current.get("skills", []),
            "tool_allowlist": ["memory", "skill_manage", "skill_view"],
            "group_reply_policy": current["group_reply_policy"],
            "default_model": current.get("default_model"),
            "features": current.get("features") or {},
            "custom_prompt": f"Controlled Feishu E2E {marker}",
            "skills_selection_mode": "explicit_allowlist",
        }
        response = self.client.patch(
            "/im/v1/agents/e2e/config", headers=self.headers, json=body
        )
        response.raise_for_status()
        _wait(
            "agent config apply",
            lambda: yaml.safe_load(config_path.read_text(encoding="utf-8")),
            lambda payload: any(
                agent.get("agent_id") == "e2e"
                and agent.get("custom_prompt") == f"Controlled Feishu E2E {marker}"
                for agent in payload.get("agents", [])
            ),
        )

    def conversation(self) -> dict[str, Any]:
        response = self.client.get("/im/v1/conversations", headers=self.headers)
        response.raise_for_status()
        matches = [
            item
            for item in response.json()["items"]
            if item.get("external_source") == "feishu"
            and item.get("config_agent_id") == "e2e"
        ]
        return matches[0] if len(matches) == 1 else {}

    def messages(self, conversation_id: str) -> list[dict[str, Any]]:
        response = self.client.get(
            f"/im/v1/conversations/{conversation_id}/messages",
            headers=self.headers,
            params={"limit": 100},
        )
        response.raise_for_status()
        return [
            item["message"]
            for item in response.json()["items"]
            if item.get("type") == "message"
        ]

    def send(self, conversation_id: str, text: str) -> None:
        response = self.client.post(
            f"/im/v1/conversations/{conversation_id}/messages",
            headers=self.headers,
            json={"sender": {"type": "user", "id": self.user_id}, "content": text},
        )
        response.raise_for_status()

    def close(self) -> None:
        self.client.close()


def _write_evolution(worktree: Path, *, skills: int, memory: int) -> None:
    path = worktree / ".gateway-workspace/e2e/.nanoassistant/config.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "self_evolution": {
                    "enabled": True,
                    "skill_creation": True,
                    "memory_curation": True,
                    "skill_nudge_interval": skills,
                    "memory_nudge_interval": memory,
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _run_journey(
    worktree: Path, fixture_url: str, profile: str, bot: str
) -> dict[str, str]:
    im = _IM(_ports(worktree)["IM_URL"])
    nonce = f"bugfix525-m3-{secrets.token_hex(6)}"
    config_path = worktree / ".gateway-config.yaml"
    try:
        _write_evolution(worktree, skills=100, memory=1)
        im.bump_agent(f"{nonce}-no-save", config_path)
        _restart_gateway(worktree, fixture_url)
        anchor_tag = f"{nonce}-route-anchor"
        _fixture_control(fixture_url, "no_save", reset=True, response_tag=anchor_tag)
        chat_id, anchor_id = _send_lark(profile, bot, f"{nonce} route anchor")
        _wait(
            "route anchor ingress",
            lambda: httpx.get(
                f"{fixture_url}/state", timeout=5, trust_env=False
            ).json(),
            lambda state: state["agent_request_index"] >= 1,
        )
        _wait(
            "route anchor reply",
            lambda: _lark_messages(profile, chat_id),
            lambda value: anchor_tag in _texts(value),
        )
        lark_baseline = _message_ids(_lark_messages(profile, chat_id))
        conversation = _wait(
            "shadow conversation",
            im.conversation,
            lambda value: bool(value.get("id")),
        )
        shadow_baseline = _message_ids(im.messages(conversation["id"]))

        _drop_session_bindings(worktree)
        no_save_tag = f"{nonce}-no-save"
        _fixture_control(fixture_url, "no_save", reset=True, response_tag=no_save_tag)
        before = _message_ids(_lark_messages(profile, chat_id))
        chat_id, seed_id = _send_lark(profile, bot, f"{nonce} no-save seed")
        _wait_lark_reply(
            profile,
            chat_id,
            before,
            "FOREGROUND-NO-SAVE-SEED",
            no_save_tag,
        )
        before = _message_ids(_lark_messages(profile, chat_id))
        _, no_save_id = _send_lark(profile, bot, f"{nonce} no-save trigger")
        _wait_lark_reply(
            profile,
            chat_id,
            before,
            "FOREGROUND-NO-SAVE-COMPLETE",
            no_save_tag,
        )
        _fixture_event(fixture_url, "no_save_review_completed")
        time.sleep(2)
        assert _NOTICE_PREFIX not in _texts(
            _messages_after(_lark_messages(profile, chat_id), lark_baseline)
        )
        assert not any(
            message.get("system_notice")
            for message in _messages_after(
                im.messages(conversation["id"]), shadow_baseline
            )
        )

        _write_evolution(worktree, skills=100, memory=1)
        im.bump_agent(f"{nonce}-failure", config_path)
        _drop_session_bindings(worktree)
        failure_tag = f"{nonce}-failure"
        _fixture_control(
            fixture_url, "memory_failure", reset=True, response_tag=failure_tag
        )
        before = _message_ids(_lark_messages(profile, chat_id))
        _send_lark(profile, bot, f"{nonce} failure seed")
        _wait_lark_reply(
            profile,
            chat_id,
            before,
            "FOREGROUND-FAILURE-SEED",
            failure_tag,
        )
        before = _message_ids(_lark_messages(profile, chat_id))
        _, failure_id = _send_lark(profile, bot, f"{nonce} failure trigger")
        _wait_lark_reply(
            profile,
            chat_id,
            before,
            "FOREGROUND-FAILURE-COMPLETE",
            failure_tag,
        )
        _fixture_event(fixture_url, "memory_failure_review_completed")
        time.sleep(2)
        assert _NOTICE_PREFIX not in _texts(
            _messages_after(_lark_messages(profile, chat_id), lark_baseline)
        )
        assert not any(
            message.get("system_notice")
            for message in _messages_after(
                im.messages(conversation["id"]), shadow_baseline
            )
        )

        _write_evolution(worktree, skills=1, memory=100)
        im.bump_agent(f"{nonce}-skill", config_path)
        _drop_session_bindings(worktree)
        skill_tag = f"{nonce}-skill"
        skill_name = f"deterministic-review-{nonce.rsplit('-', 1)[-1]}"
        _fixture_control(
            fixture_url,
            "skill_create",
            reset=True,
            response_tag=skill_tag,
            skill_name=skill_name,
        )
        before = _message_ids(_lark_messages(profile, chat_id))
        _, skill_id = _send_lark(profile, bot, f"{nonce} skill trigger")
        _wait_lark_reply(
            profile,
            chat_id,
            before,
            "FOREGROUND-SKILL-COMPLETE",
            skill_tag,
        )
        _fixture_event(fixture_url, "skill_review_waiting")
        _fixture_control(fixture_url, "skill_create", release_review=True)
        _fixture_event(fixture_url, "skill_review_completed")
        _wait(
            "one external skill receipt",
            lambda: _lark_messages(profile, chat_id),
            lambda value: (
                _texts(_messages_after(value, lark_baseline)).count(_NOTICE) == 1
            ),
        )
        _wait(
            "one shadow skill receipt",
            lambda: im.messages(conversation["id"]),
            lambda value: (
                sum(
                    (message.get("system_notice") or {}).get("updated_targets")
                    == ["skills"]
                    for message in _messages_after(value, shadow_baseline)
                )
                == 1
            ),
        )

        _write_evolution(worktree, skills=100, memory=1)
        im.bump_agent(f"{nonce}-shadow-memory", config_path)
        _drop_session_bindings(worktree)
        memory_tag = f"{nonce}-shadow-memory"
        _fixture_control(fixture_url, "memory_add", reset=True, response_tag=memory_tag)
        im.send(conversation["id"], f"{nonce} shadow memory seed")
        _wait(
            "shadow memory seed",
            lambda: im.messages(conversation["id"]),
            lambda value: (
                "FOREGROUND-MEMORY-SEED"
                in _texts(_messages_after(value, shadow_baseline))
                and memory_tag in _texts(_messages_after(value, shadow_baseline))
            ),
        )
        im.send(conversation["id"], f"{nonce} shadow memory trigger")
        _wait(
            "shadow memory foreground",
            lambda: im.messages(conversation["id"]),
            lambda value: (
                "FOREGROUND-MEMORY-COMPLETE"
                in _texts(_messages_after(value, shadow_baseline))
                and memory_tag in _texts(_messages_after(value, shadow_baseline))
            ),
        )
        _fixture_event(fixture_url, "memory_add_review_completed")
        _wait(
            "one shadow memory receipt",
            lambda: im.messages(conversation["id"]),
            lambda value: (
                sum(
                    (message.get("system_notice") or {}).get("updated_targets")
                    == ["memory"]
                    for message in _messages_after(value, shadow_baseline)
                )
                == 1
            ),
        )
        time.sleep(2)
        final_lark = _messages_after(_lark_messages(profile, chat_id), lark_baseline)
        assert _texts(final_lark).count(_NOTICE) == 1
        final_shadow = _messages_after(im.messages(conversation["id"]), shadow_baseline)
        visible = _texts(final_lark) + "\n" + _texts(final_shadow)
        assert not any(marker in visible for marker in _RAW_MARKERS)
        skill_path = (
            worktree
            / f".gateway-workspace/e2e/.nanoassistant/skills/{skill_name}/SKILL.md"
        )
        assert skill_path.is_file()
        config = im.client.get("/im/v1/agents/e2e/config", headers=im.headers).json()
        assert skill_name in config["skills"]
        return {
            "nonce": nonce,
            "chat_id": chat_id,
            "anchor_message_id": anchor_id,
            "seed_message_id": seed_id,
            "no_save_message_id": no_save_id,
            "failure_message_id": failure_id,
            "skill_message_id": skill_id,
            "shadow_conversation_id": conversation["id"],
            "skill_name": skill_name,
        }
    finally:
        im.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wt", required=True, type=Path)
    parser.add_argument(
        "--env",
        type=Path,
        default=Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "nano-multiagent/feishu-e2e.env",
    )
    args = parser.parse_args()
    worktree = args.wt.resolve()
    _require_feishu_stack(worktree)
    values = load_e2e_env(args.env)
    profile = values["NANO_MULTIAGENT_E2E_FEISHU_LARK_PROFILE"]
    status_result = subprocess.run(
        ["lark-cli", "--profile", profile, "auth", "status", "--json", "--verify"],
        capture_output=True,
        text=True,
        check=False,
    )
    status = json.loads(status_result.stdout) if status_result.returncode == 0 else {}
    _require_test_profile(status, values, profile)
    fixture: subprocess.Popen[str] | None = None
    try:
        fixture, fixture_url = _start_fixture(worktree)
        evidence = _run_journey(
            worktree,
            fixture_url,
            profile,
            values["NANO_MULTIAGENT_E2E_FEISHU_BOT_OPEN_ID"],
        )
        print(json.dumps(evidence, sort_keys=True))
    finally:
        if fixture is not None:
            _stop_process(fixture)
        (worktree / ".feishu-self-evolution-llm.jsonl").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
