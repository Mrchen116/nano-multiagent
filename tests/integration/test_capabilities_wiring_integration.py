from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app
from nano_multiagent.tools.base import ToolContext
from nano_multiagent.tools.registry import ToolRegistry


class _CustomPingTool:
    name = "custom_ping"
    description = "custom ping"
    input_schema = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": ["value"],
        "additionalProperties": False,
    }

    def run(self, args, ctx):  # pragma: no cover - helper stub
        del ctx
        return {"echo": args["value"]}


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_capabilities_reflects_injected_tool_registry(tmp_path: Path) -> None:
    registry = ToolRegistry(context=ToolContext.create(repo_root=tmp_path))
    registry.register(_CustomPingTool())

    client = TestClient(
        create_app(
            repo_root=tmp_path,
            tool_registry=registry,
            auth_token="test-token",
        )
    )

    response = client.get("/v1/capabilities", headers=_auth_headers("req-cap-integration"))

    assert response.status_code == 200
    names = [item["name"] for item in response.json()["tools"]]
    assert names == ["custom_ping"]
