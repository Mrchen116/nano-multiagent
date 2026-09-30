"""RPC results must pass a queued mutation on the same Gateway connection."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import WebSocketDisconnect
from IM.ws.gateway.runtime import GatewayRuntime


def test_rpc_result_passes_earlier_frame_waiting_for_http_admission_gate():
    async def journey():
        gate = asyncio.Lock()
        await gate.acquire()
        incoming = asyncio.Queue()
        rpc_received = asyncio.Event()
        seen = []

        async def receive():
            item = await incoming.get()
            if item is None:
                raise WebSocketDisconnect()
            return json.dumps(item)

        socket = SimpleNamespace(
            scope={"app": SimpleNamespace(state=SimpleNamespace(company_gate=gate))},
            accept=AsyncMock(),
            receive_text=receive,
            send_json=AsyncMock(),
            close=AsyncMock(),
        )
        runtime = GatewayRuntime(
            sessions=SimpleNamespace(disconnect=AsyncMock()),
            control=None,
            channel_control=None,
            relay=None,
            execution=None,
        )

        async def handle(**kwargs):
            seen.append(kwargs["message_type"])
            if kwargs["message_type"] == "agent.config.apply.result":
                rpc_received.set()
            return None

        runtime.handle_message = handle
        await incoming.put({"type": "node.heartbeat", "payload": {}})
        await incoming.put({"type": "agent.config.apply.result", "payload": {}})
        serving = asyncio.create_task(runtime.serve(socket))
        try:
            await asyncio.wait_for(rpc_received.wait(), 0.3)
            assert seen == ["agent.config.apply.result"]
            gate.release()
            for _ in range(10):
                await asyncio.sleep(0)
            assert seen == ["agent.config.apply.result", "node.heartbeat"]
        finally:
            if gate.locked():
                gate.release()
            await incoming.put(None)
            await serving

    asyncio.run(journey())
