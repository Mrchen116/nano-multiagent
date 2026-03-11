"""Unit tests: create_app accepts an optional ProductProfile."""

from pathlib import Path

from fastapi import FastAPI

from agent.core.agent.prompting import CODING_SYSTEM_PROMPT
from agent.products.base import ProductProfile
from agent.products.local_coding import LOCAL_CODING_PROFILE
from agent.platform.http_api.app import create_app
from agent.platform.persistence.session.sqlite_store import SQLiteSessionStore


def _make_profile(global_home: Path) -> ProductProfile:
    return ProductProfile(
        product_id="test_product",
        display_name="Test",
        config_namespace="test",
        global_config_home=global_home,
        workspace_config_dirname=".testproduct",
        session_db_filename="sessions.sqlite3",
    )


def _session_store_path(app: FastAPI) -> Path:
    store = app.state.session_service.manager._store  # type: ignore[attr-defined]
    assert isinstance(store, SQLiteSessionStore)
    return store._db_path.resolve()


def test_create_app_with_local_coding_profile_returns_fastapi() -> None:
    """create_app with explicit local_coding profile must return a FastAPI app."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE)
    assert isinstance(app, FastAPI)


def test_create_app_with_profile_has_tool_registry() -> None:
    """app wired via profile must have a tool registry on its state."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE)
    assert app.state.tool_registry is not None


def test_create_app_with_profile_has_hook_registry() -> None:
    """app wired via profile must have a hook registry on its state."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE)
    assert app.state.hook_registry is not None


def test_create_app_without_profile_still_works() -> None:
    """Backward-compatible: create_app() without profile preserves existing behavior."""
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.state.tool_registry is not None


def test_create_app_with_minimal_profile() -> None:
    """create_app should accept a minimal custom profile."""
    profile = ProductProfile(
        product_id="test_product",
        display_name="Test",
        config_namespace="test",
    )
    app = create_app(product_profile=profile)
    assert isinstance(app, FastAPI)
    assert app.state.hook_registry is not None


def test_create_app_with_profile_uses_resolved_system_prompt() -> None:
    """app wired via local_coding profile must inject CODING_SYSTEM_PROMPT into runtime."""
    app = create_app(product_profile=LOCAL_CODING_PROFILE)
    runtime = app.state.agent_runtime
    loop = getattr(runtime, "_loop", None)
    assert loop is not None
    assert loop._system_prompt == CODING_SYSTEM_PROMPT


def test_create_app_with_profile_uses_profile_session_store_path(tmp_path: Path) -> None:
    """create_app should pass product_profile into SessionService path resolution."""
    profile = _make_profile(tmp_path / ".testproduct")
    app = create_app(product_profile=profile)
    assert _session_store_path(app) == (tmp_path / ".testproduct" / "sessions.sqlite3").resolve()


def test_create_app_with_profile_exposes_runtime_config_resolver(tmp_path: Path) -> None:
    profile = _make_profile(tmp_path / ".testproduct")

    app = create_app(product_profile=profile, repo_root=tmp_path)

    runtime = app.state.agent_runtime
    resolver = getattr(runtime, "config_resolver", None)
    assert resolver is not None
    assert resolver.workspace_config_root() == tmp_path / ".testproduct"


def test_create_app_with_profile_uses_resolver_skill_roots_over_legacy_codex(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / ".codex-home"))
    profile = _make_profile(tmp_path / ".testproduct-global")
    skill_root = tmp_path / ".testproduct" / "skills" / "resolver-skill"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "---\nname: resolver-skill\ndescription: resolver skill\n---\nresolver skill\n",
        encoding="utf-8",
    )
    legacy_root = tmp_path / ".codex" / "skills" / "legacy-skill"
    legacy_root.mkdir(parents=True)
    (legacy_root / "SKILL.md").write_text(
        "---\nname: legacy-skill\ndescription: legacy skill\n---\nlegacy skill\n",
        encoding="utf-8",
    )

    app = create_app(product_profile=profile, repo_root=tmp_path)

    runtime = app.state.agent_runtime
    available_skills = getattr(runtime._loop, "_available_skills")
    available_names = {skill.name for skill in available_skills}
    assert "resolver-skill" in available_names
    assert "legacy-skill" not in available_names
