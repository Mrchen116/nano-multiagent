from pathlib import Path

from fastapi.testclient import TestClient

from nano_multiagent.server.app import create_app


def _auth_headers(request_id: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Request-Id": request_id,
    }


def test_tools_endpoint_lists_builtin_and_directory_tools(tmp_path: Path) -> None:
    tools_dir = tmp_path / ".nano" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    (tools_dir / "reverse_tool.py").write_text(
        """
class ReverseTool:
    name = \"reverse\"
    description = \"Reverse text\"
    input_schema = {
        \"type\": \"object\",
        \"properties\": {\"text\": {\"type\": \"string\"}},
        \"required\": [\"text\"],
        \"additionalProperties\": False,
    }

    def run(self, args, ctx):
        return {\"text\": args[\"text\"][::-1]}

TOOL = ReverseTool()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(create_app(repo_root=tmp_path, auth_token="test-token"))

    response = client.get("/v1/tools", headers=_auth_headers("req-tools-e2e"))

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-tools-e2e"
    names = {item["name"] for item in response.json()["tools"]}
    assert {"read", "write", "edit", "bash", "reverse"}.issubset(names)

