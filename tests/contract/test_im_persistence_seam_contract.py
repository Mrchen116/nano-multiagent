"""Architecture contract for IM persistence callers."""

import ast
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[2]
_CALLERS = (
    "src/IM/application/event_service.py",
    "src/IM/application/web_im_service.py",
    "src/IM/api/routes/web_im.py",
)


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


def _attribute_references(relative_path: str, attribute: str) -> list[ast.Attribute]:
    tree = ast.parse(_source(relative_path))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == attribute
    ]


def test_web_im_callers_do_not_execute_persistence_operations() -> None:
    """Keep application and HTTP callers behind repository/service interfaces."""
    for relative_path in _CALLERS:
        source = _source(relative_path)
        assert "._connection" not in source, relative_path
        assert not _attribute_calls(relative_path, "execute"), relative_path
        assert not _attribute_calls(relative_path, "commit"), relative_path


def test_api_dependencies_only_construct_conversation_repository() -> None:
    """Prevent API composition from regaining a SQL-owning repository subclass."""
    relative_path = "src/IM/api/deps.py"
    tree = ast.parse(_source(relative_path))
    subclasses = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "ConversationRepository"
            for base in node.bases
        )
    ]
    assert not subclasses
    assert not _attribute_calls(relative_path, "execute")
    assert not _attribute_calls(relative_path, "commit")


def test_user_stream_does_not_execute_persistence_operations() -> None:
    """Keep user-stream lifecycle behind event and Gateway persistence interfaces."""
    relative_path = "src/IM/ws/user_stream.py"
    assert not _attribute_references(relative_path, "_connection")
    assert not _attribute_calls(relative_path, "execute")
    assert not _attribute_calls(relative_path, "commit")


def test_gateway_handler_node_lifecycle_uses_only_gateway_persistence() -> None:
    """Prevent node/profile/user registration SQL from returning to the handler."""
    source = _source("src/IM/ws/gateway_handler.py")
    assert "_node_repository" not in source
    assert "AgentProfileRepository" not in source
    assert "GatewayNodePersistence" in source


def test_gateway_handler_delivery_uses_only_gateway_persistence() -> None:
    """Keep delivery SQL and owner policy behind the conversation persistence seam."""
    relative_path = "src/IM/ws/gateway_handler.py"
    source = _source(relative_path)
    assert "GatewayConversationPersistence" in source
    assert not _attribute_references(relative_path, "_connection")
    assert not _attribute_calls(relative_path, "execute")
    assert not _attribute_calls(relative_path, "commit")
    assert "caller_owner_id=None" in source
    assert "UserRepository" not in source


def test_app_wires_gateway_delivery_collaborators_explicitly() -> None:
    """Require the composition root to inject persistence and message collaborators."""
    source = _source("src/IM/app.py")
    assert "GatewayConversationPersistence(connection)" in source
    assert "conversation_persistence=conversation_persistence" in source
    assert "message_repository=message_repository" in source


def test_event_replay_result_is_owned_only_by_infra() -> None:
    """Keep replay result ownership one-way from WS into infra."""
    definitions: list[str] = []
    for relative_path in (
        "src/IM/infra/repositories.py",
        "src/IM/ws/user_stream.py",
        "src/IM/application/event_service.py",
    ):
        tree = ast.parse(_source(relative_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "EventReplayResult"
            for node in ast.walk(tree)
        ):
            definitions.append(relative_path)
    assert definitions == ["src/IM/infra/repositories.py"]
    assert "IM.ws" not in _source("src/IM/infra/repositories.py")


def test_web_im_route_receives_profile_repository_as_dependency() -> None:
    """Keep route business reads off the app-scoped raw connection."""
    source = _source("src/IM/api/routes/web_im.py")
    assert "request.app.state.connection" not in source
    assert "AgentProfileRepository(request.app.state.connection)" not in source
    assert "Depends(get_profile_repository)" in source
