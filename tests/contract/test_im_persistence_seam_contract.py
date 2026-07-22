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


def test_repositories_use_domain_modules_without_legacy_aggregate() -> None:
    """Keep durable aggregates in their canonical modules without a facade."""
    repository_root = _ROOT / "src/IM/infra/repositories"
    expected_modules = {
        "users.py",
        "settings.py",
        "conversations.py",
        "messages.py",
        "agents.py",
        "nodes.py",
        "bindings.py",
        "metrics.py",
        "events.py",
        "config_boundaries.py",
        "_event_rows.py",
        "_message_projection.py",
    }
    assert repository_root.is_dir()
    assert expected_modules <= {path.name for path in repository_root.iterdir()}
    assert not (_ROOT / "src/IM/infra/repositories.py").exists()
    assert _source("src/IM/infra/repositories/__init__.py").strip() == ""


def test_event_replay_result_is_owned_only_by_event_repository() -> None:
    """Keep replay result ownership one-way from WS into infra."""
    definitions: list[str] = []
    for relative_path in (
        "src/IM/infra/repositories/events.py",
        "src/IM/ws/user_stream.py",
        "src/IM/application/event_service.py",
    ):
        tree = ast.parse(_source(relative_path))
        if any(
            isinstance(node, ast.ClassDef) and node.name == "EventReplayResult"
            for node in ast.walk(tree)
        ):
            definitions.append(relative_path)
    assert definitions == ["src/IM/infra/repositories/events.py"]
    assert "IM.ws" not in _source("src/IM/infra/repositories/events.py")


def test_event_row_primitive_is_private_and_transaction_neutral() -> None:
    """Prevent shared event rows from becoming a committing public repository."""
    source = _source("src/IM/infra/repositories/_event_rows.py")
    assert "def insert_event_row(" in source
    assert ".commit(" not in source
    assert "notify" not in source
    for relative_path in (
        "src/IM/infra/repositories/messages.py",
        "src/IM/infra/repositories/events.py",
        "src/IM/infra/repositories/config_boundaries.py",
    ):
        assert "IM.infra.repositories._event_rows" in _source(relative_path)


def test_repository_package_has_no_aggregate_reexports() -> None:
    """Require callers to name their actual aggregate dependency."""
    source = _source("src/IM/infra/repositories/__init__.py")
    assert "import " not in source
    assert "__all__" not in source


def test_web_im_route_receives_profile_repository_as_dependency() -> None:
    """Keep route business reads off the app-scoped raw connection."""
    source = _source("src/IM/api/routes/web_im.py")
    assert "request.app.state.connection" not in source
    assert "AgentProfileRepository(request.app.state.connection)" not in source
    assert "Depends(get_profile_repository)" in source
