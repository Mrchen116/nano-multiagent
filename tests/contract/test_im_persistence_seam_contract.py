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


def test_user_stream_has_only_the_m2_stale_node_sql_exception() -> None:
    """Keep M1 event paths clean while enumerating the one M2-owned legacy query."""
    relative_path = "src/IM/ws/user_stream.py"
    source = _source(relative_path)
    assert source.count("node_repository._connection.execute") == 1
    assert source.count("._connection") == 1
    assert len(_attribute_calls(relative_path, "execute")) == 1
    assert not _attribute_calls(relative_path, "commit")
    assert "SELECT node_id FROM nodes" in source


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
