"""Acceptance coverage for realistic IM↔Gateway end-to-end chains in M106."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from IM.app import create_app
from personal_assistant.channels.base import InboundMessage, OutboundMessage
from personal_assistant.config.local_store import AgentWorkspaceConfig
from personal_assistant.gateway.channel_registry import ChannelRegistry
from personal_assistant.gateway.inbound_pipeline import InboundPipeline
from personal_assistant.gateway.outbound_router import OutboundRouter
from personal_assistant.gateway.run_queue import SessionRunQueue
from personal_assistant.gateway.session_keys import SessionBindingStore


class RecordingWebRelayAdapter:
    """Act as a process-local Web IM relay channel for acceptance tests.

    Args:
        name: Stable adapter name registered in the gateway channel registry.
    """

    def __init__(self, name: str = "web_relay") -> None:
        self.name = name
        self.started_with = None
        self.sent: list[OutboundMessage] = []
        self.inbound: list[InboundMessage] = []

    def start(self, on_inbound) -> None:  # noqa: ANN001
        """Store the inbound callback used by the gateway bootstrap path."""

        self.started_with = on_inbound

    def send(self, outbound: OutboundMessage) -> None:
        """Record one outbound reply routed back to Web IM."""

        self.sent.append(outbound)

    def stop(self) -> None:
        """Provide the channel protocol stop hook for completeness."""

    def from_relay_payload(self, payload: dict[str, object]) -> InboundMessage:
        """Convert one IM relay.message payload into a gateway inbound envelope."""

        message = payload["message"]
        assert isinstance(message, dict)
        sender_user_id = str(message["sender_user_id"])
        conversation_id = str(payload["conversation_id"])
        metadata = {
            "relay_task_id": payload["relay_task_id"],
            "message_id": message["id"],
            "idempotency_key": payload["idempotency_key"],
            "sender_type": message["sender_type"],
        }
        inbound = InboundMessage(
            channel_name=self.name,
            text=str(message["content"]),
            external_user_id=sender_user_id,
            external_chat_id=conversation_id,
            is_group=False,
            metadata=metadata,
        )
        self.inbound.append(inbound)
        return inbound


class StubKernelClient:
    """Provide deterministic kernel behavior for realistic gateway acceptance tests."""

    def __init__(self) -> None:
        self.create_session_calls: list[dict[str, str | None]] = []
        self.send_calls: list[dict[str, Any]] = []
        self.run_states: dict[str, dict[str, object]] = {}
        self._session_index = 0
        self._run_index = 0

    def create_session(
        self,
        *,
        workspace_root: str,
        product_id: str,
        title: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> dict[str, str]:
        self._session_index += 1
        self.create_session_calls.append(
            {
                "workspace_root": workspace_root,
                "product_id": product_id,
                "title": title,
                "metadata": metadata,
            }
        )
        return {"session_id": f"sess-{self._session_index}"}

    def send_message_async(
        self,
        *,
        session_id: str,
        texts: list[str],
        image_urls: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        if not texts:
            raise ValueError("texts must contain at least one message")
        self._run_index += 1
        run_id = f"run-{self._run_index}"
        combined_text = "\n".join(texts)
        self.send_calls.append(
            {
                "session_id": session_id,
                "texts": list(texts),
                "image_urls": image_urls,
                "run_id": run_id,
            }
        )
        self.run_states[run_id] = {
            "run_id": run_id,
            "status": "completed",
            "output_text": f"assistant:{combined_text}",
        }
        return {"run_id": run_id}

    def get_run(self, *, run_id: str) -> dict[str, object]:
        return self.run_states[run_id]


class GatewayAcceptanceHarness:
    """Compose IM app, relay websocket, and gateway pipeline for acceptance runs."""

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path
        self.app = create_app(db_path=tmp_path / "im.db")
        self.adapter = RecordingWebRelayAdapter()
        self.kernel_client = StubKernelClient()
        self._workspace_root = tmp_path / "agent-alpha"
        self._workspace_root.mkdir()
        self.pipeline = InboundPipeline(
            kernel_client=self.kernel_client,
            agents=(
                AgentWorkspaceConfig(
                    agent_id="agent-alpha",
                    workspace_root=self._workspace_root,
                    title="Agent Alpha",
                ),
            ),
            outbound_router=OutboundRouter(ChannelRegistry((self.adapter,))),
            run_queue=SessionRunQueue(),
            session_store=SessionBindingStore(),
            default_agent_id="agent-alpha",
        )

    def run_roundtrip(self) -> dict[str, object]:
        """Execute one realistic bind->connect->relay->reply->receipt chain."""

        with TestClient(self.app) as client:
            user_id = self._create_user(client, username="alice")
            bind_started = client.post("/im/v1/bind", json={"action": "start", "node_id": "node-1"})
            if bind_started.status_code == 404:
                self._seed_node(client)
                bind_started = client.post("/im/v1/bind", json={"action": "start", "node_id": "node-1"})
            assert bind_started.status_code == 201
            bind_body = bind_started.json()
            bind_confirmed = client.post(
                "/im/v1/bind",
                json={"action": "confirm", "bind_id": bind_body["bind_id"], "user_id": user_id},
            )
            assert bind_confirmed.status_code == 201

            conversation_id = self._create_conversation(client, participant_ids=[user_id])
            with client.websocket_connect("/im/ws/gateway") as websocket:
                websocket.send_json(
                    {
                        "type": "node.register",
                        "payload": {
                            "node_id": "node-1",
                            "node_name": "MacBook",
                            "version": "1.0.0",
                            "agents": ["agent-alpha"],
                            "capabilities": {"relay": True},
                        },
                    }
                )
                register_ack = websocket.receive_json()
                websocket.send_json(
                    {
                        "type": "node.heartbeat",
                        "payload": {
                            "node_id": "node-1",
                            "status": "online",
                            "agent_count": 1,
                            "version": "1.0.0",
                        },
                    }
                )
                heartbeat_ack = websocket.receive_json()

                created = client.post(
                    f"/im/v1/conversations/{conversation_id}/messages",
                    headers={"Idempotency-Key": "accept-1"},
                    json={
                        "sender_user_id": user_id,
                        "content": "hello from web im",
                        "target_node_id": "node-1",
                    },
                )
                assert created.status_code == 201
                relay_frame = websocket.receive_json()
                inbound = self.adapter.from_relay_payload(relay_frame["payload"])
                pipeline_result = asyncio.run(self.pipeline.handle_inbound(inbound))
                relay_task_id = str(relay_frame["payload"]["relay_task_id"])

                websocket.send_json(
                    {
                        "type": "node.delivery_receipt",
                        "payload": {
                            "node_id": "node-1",
                            "relay_task_id": relay_task_id,
                            "delivery_status": "sent",
                            "detail": f"run_id={pipeline_result.run_id}",
                        },
                    }
                )
                sent_ack = websocket.receive_json()
                websocket.send_json(
                    {
                        "type": "node.report",
                        "payload": {
                            "node_id": "node-1",
                            "run_id": pipeline_result.run_id,
                            "conversation_id": conversation_id,
                            "message_id": relay_frame["payload"]["message"]["id"],
                            "summary": pipeline_result.reply_text,
                            "status": "running",
                        },
                    }
                )
                report_ack = websocket.receive_json()
                websocket.send_json(
                    {
                        "type": "node.delivery_receipt",
                        "payload": {
                            "node_id": "node-1",
                            "relay_task_id": relay_task_id,
                            "delivery_status": "completed",
                            "detail": pipeline_result.reply_text,
                        },
                    }
                )
                completed_ack = websocket.receive_json()
                report_snapshot = asyncio.run(
                    self.app.state.gateway_handler.snapshot_connection(node_id="node-1")
                )
                assert report_snapshot is not None
                reports = list(report_snapshot.reports)

            me_snapshot = client.get(f"/im/v1/me?user_id={user_id}")
            messages = client.get(f"/im/v1/conversations/{conversation_id}/messages")
            event_rows = self.app.state.connection.execute(
                """
                SELECT event_id, event_type, delivery_status, payload_json
                FROM conversation_events
                WHERE conversation_id = ?
                ORDER BY event_id
                """,
                (conversation_id,),
            ).fetchall()
            events = []
            for r in event_rows:
                raw = json.loads(str(r["payload_json"]))
                base = raw if isinstance(raw, dict) else {}
                # 与 IM 用户流 wire data 一致：delivery_status 来自列，不一定重复出现在 payload_json
                events.append(
                    {
                        "id": int(r["event_id"]),
                        "event": str(r["event_type"]),
                        "data": {**base, "delivery_status": str(r["delivery_status"])},
                    }
                )
            nodes = client.get("/im/v1/nodes")
            relay_row = self.app.state.connection.execute(
                "SELECT status, receipt_status, receipt_detail FROM relay_tasks WHERE relay_task_id = ?",
                (relay_task_id,),
            ).fetchone()
            assert relay_row is not None
            return {
                "bind_url": bind_body["bind_url"],
                "register_ack": register_ack,
                "heartbeat_ack": heartbeat_ack,
                "sent_ack": sent_ack,
                "report_ack": report_ack,
                "completed_ack": completed_ack,
                "me": me_snapshot.json(),
                "messages": messages.json(),
                "events": events,
                "nodes": nodes.json(),
                "relay_status": {
                    "status": relay_row["status"],
                    "receipt_status": relay_row["receipt_status"],
                    "receipt_detail": relay_row["receipt_detail"],
                },
                "reports": reports,
                "adapter_outbound": [outbound.text for outbound in self.adapter.sent],
                "pipeline": {
                    "session_key": pipeline_result.session_key,
                    "kernel_session_id": pipeline_result.kernel_session_id,
                    "run_id": pipeline_result.run_id,
                    "reply_text": pipeline_result.reply_text,
                },
            }

    def _seed_node(self, client: TestClient) -> None:
        client.app.state.connection.execute(
            "INSERT INTO nodes(node_id, owner_id, node_name, status, last_heartbeat_at, agent_count, version, last_error) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("node-1", None, "MacBook", "offline", "1970-01-01T00:00:00Z", 0, "", None),
        )
        client.app.state.connection.commit()

    @staticmethod
    def _create_user(client: TestClient, *, username: str) -> str:
        response = client.post(
            "/im/v1/users",
            json={"username": username, "display_name": username.title()},
        )
        assert response.status_code == 201
        return response.json()["id"]

    @staticmethod
    def _create_conversation(client: TestClient, *, participant_ids: list[str]) -> str:
        response = client.post(
            "/im/v1/conversations",
            json={"title": "Web IM", "participant_ids": participant_ids},
        )
        assert response.status_code == 201
        return response.json()["id"]


def test_im_gateway_acceptance_covers_bind_connect_roundtrip_and_receipts(tmp_path: Path) -> None:
    """Run the realistic M106 acceptance chain through IM HTTP, WS, and gateway pipeline."""

    harness = GatewayAcceptanceHarness(tmp_path)
    result = harness.run_roundtrip()

    assert result["bind_url"].startswith("http://testserver/bind/confirm?token=")
    assert result["register_ack"] == {
        "type": "ack",
        "payload": {"message_type": "node.register", "node_id": "node-1"},
    }
    assert result["heartbeat_ack"] == {
        "type": "ack",
        "payload": {"message_type": "node.heartbeat", "node_id": "node-1"},
    }
    assert result["sent_ack"]["payload"]["status"] == "sent"
    assert result["report_ack"] == {
        "type": "ack",
        "payload": {"message_type": "node.report", "node_id": "node-1"},
    }
    assert result["completed_ack"]["payload"]["status"] == "completed"
    assert result["me"]["owned_node_ids"] == ["node-1"]
    assert result["messages"]["items"][0]["content"] == "hello from web im"
    assert result["adapter_outbound"] == ["assistant:hello from web im"]
    assert result["pipeline"]["reply_text"] == "assistant:hello from web im"
    assert result["relay_status"] == {
        "status": "completed",
        "receipt_status": "completed",
        "receipt_detail": "assistant:hello from web im",
    }
    assert result["nodes"][0]["status"] == "offline"
    assert result["heartbeat_ack"]["payload"]["node_id"] == "node-1"
    assert result["reports"][0]["status"] == "running"
    assert result["reports"] == [
        {
            "node_id": "node-1",
            "run_id": result["pipeline"]["run_id"],
            "conversation_id": result["messages"]["items"][0]["conversation_id"],
            "message_id": result["messages"]["items"][0]["id"],
            "summary": "assistant:hello from web im",
            "status": "running",
        }
    ]
    event_names = [event["event"] for event in result["events"]]
    assert event_names == [
        "message.sent",
        "relay.accepted",
        "relay.processing",
        "relay.completed",
        "message.delivered",
    ]
    accepted_event = result["events"][1]["data"]
    processing_event = result["events"][2]["data"]
    completed_event = result["events"][3]["data"]
    delivered_event = result["events"][4]["data"]
    assert accepted_event["progress_state"] == "accepted"
    assert processing_event["progress_state"] == "processing"
    assert processing_event["run_id"] == result["pipeline"]["run_id"]
    assert completed_event["progress_state"] == "completed"
    assert completed_event["detail"] == "assistant:hello from web im"
    assert delivered_event["delivery_status"] == "completed"
    assert delivered_event["progress_state"] == "completed"
    assert delivered_event["semantic"] == "agent_run_completed"


def test_im_gateway_acceptance_surfaces_failure_feedback_in_conversation_sse(tmp_path: Path) -> None:
    """Expose actionable relay failure feedback inside the conversation event stream."""

    harness = GatewayAcceptanceHarness(tmp_path)
    result = harness.run_roundtrip()

    event_names = [event["event"] for event in result["events"]]
    assert "relay.failed" not in event_names
    assert "conversation.notice" not in event_names
    assert "message.delivered" in event_names
