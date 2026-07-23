"""Architecture contract for IM Gateway websocket modules."""

import ast
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_GATEWAY_ROOT = _ROOT / "src/IM/ws/gateway"
_EXPECTED_MODULES = {
    "__init__.py",
    "runtime.py",
    "sessions.py",
    "control.py",
    "channel_control.py",
    "relay.py",
    "execution.py",
    "protocol.py",
}


def _source(relative_path: str) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _attribute_calls(relative_path: str, attribute: str) -> list[ast.Call]:
    tree = ast.parse(_source(relative_path))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


def test_gateway_package_replaces_legacy_modules() -> None:
    """Keep the final Gateway boundary as concrete focused modules."""
    assert _GATEWAY_ROOT.is_dir()
    assert _EXPECTED_MODULES <= {path.name for path in _GATEWAY_ROOT.iterdir()}
    assert not (_ROOT / "src/IM/ws/gateway_handler.py").exists()
    assert not (_ROOT / "src/IM/ws/gateway_protocol.py").exists()
    assert _source("src/IM/ws/gateway/__init__.py").strip() == ""


def test_runtime_only_dispatches_protocol_frames() -> None:
    """Keep transport dispatch separate from persistence and workflow ownership."""
    source = _source("src/IM/ws/gateway/runtime.py")
    assert "class GatewayRuntime" in source
    assert "GatewayNodePersistence" not in source
    assert "EventBridge" not in source
    assert "ChannelControlStore" not in source
    assert not _attribute_calls("src/IM/ws/gateway/runtime.py", "execute")
    assert not _attribute_calls("src/IM/ws/gateway/runtime.py", "commit")


def test_gateway_owners_keep_sql_out_of_websocket_transport() -> None:
    """Keep Gateway orchestration dependent on existing concrete collaborators."""
    for relative_path in (
        "src/IM/ws/gateway/sessions.py",
        "src/IM/ws/gateway/control.py",
        "src/IM/ws/gateway/channel_control.py",
        "src/IM/ws/gateway/relay.py",
        "src/IM/ws/gateway/execution.py",
    ):
        source = _source(relative_path)
        assert "self._connection =" not in source, relative_path
        assert not _attribute_calls(relative_path, "execute"), relative_path
        assert not _attribute_calls(relative_path, "commit"), relative_path


def test_app_wires_gateway_collaborators_explicitly() -> None:
    """Require composition root to expose concrete route-facing Gateway modules."""
    source = _source("src/IM/app.py")
    for module_name in (
        "GatewaySessions",
        "GatewayControl",
        "GatewayChannelControl",
        "GatewayRelay",
        "GatewayExecution",
        "GatewayRuntime",
    ):
        assert module_name in source


def test_routes_depend_on_narrow_gateway_modules() -> None:
    """Prevent a unified Gateway transport facade from returning through API deps."""
    source = _source("src/IM/api/deps.py")
    assert "get_gateway_handler" not in source
    assert "GatewayHandler" not in source
    for getter in (
        "get_gateway_sessions",
        "get_gateway_control",
        "get_gateway_channel_control",
        "get_gateway_relay",
    ):
        assert f"def {getter}" in source
