"""Integration tests: bootstrap_product(PERSONAL_ASSISTANT_PROFILE) end-to-end (M77).

Verifies that the personal_assistant product boots correctly via the shared
bootstrap_product() path without requiring any product-specific branching in
the runtime or server.
"""

from pathlib import Path

from nano_multiagent.platform.bootstrap import bootstrap_product
from nano_multiagent.platform.config.resolver import ConfigResolver
from nano_multiagent.platform.product import ResolvedProductConfig
from nano_multiagent.platform.products.local_coding import LOCAL_CODING_PROFILE
from nano_multiagent.platform.products.personal_assistant import (
    PERSONAL_ASSISTANT_PROFILE,
)


def test_bootstrap_personal_assistant_returns_resolved_config(tmp_path: Path) -> None:
    """bootstrap_product(PERSONAL_ASSISTANT_PROFILE) must return a ResolvedProductConfig."""
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert isinstance(resolved, ResolvedProductConfig)


def test_bootstrap_personal_assistant_product_id(tmp_path: Path) -> None:
    """Resolved config must carry the personal_assistant product_id."""
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.product_id == "personal_assistant"


def test_bootstrap_personal_assistant_resolved_system_prompt_non_empty(tmp_path: Path) -> None:
    """Resolved system prompt must be non-empty for personal_assistant."""
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.resolved_system_prompt
    assert len(resolved.resolved_system_prompt.strip()) > 0


def test_bootstrap_personal_assistant_tool_registry_only_read_and_task(tmp_path: Path) -> None:
    """personal_assistant bootstrap must produce exactly {read, task} tool registry."""
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.tool_registry is not None
    tool_names = {spec.name for spec in resolved.tool_registry.list_specs()}
    assert tool_names == {"read", "task"}


def test_bootstrap_personal_assistant_hook_registry_no_bash_risk_gate(tmp_path: Path) -> None:
    """personal_assistant hook registry must not contain bash_risk_gate."""
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.hook_registry is not None
    module_stems = {
        Path(h.file_path).stem
        for h in resolved.hook_registry.all_handlers()
        if h.file_path is not None
    }
    assert "bash_risk_gate" not in module_stems


def test_bootstrap_personal_assistant_hook_registry_has_default_status_and_usage_metrics(
    tmp_path: Path,
) -> None:
    """personal_assistant hook registry must include default_status and usage_metrics."""
    resolved = bootstrap_product(profile=PERSONAL_ASSISTANT_PROFILE, repo_root=tmp_path)
    assert resolved.hook_registry is not None
    module_stems = {
        Path(h.file_path).stem
        for h in resolved.hook_registry.all_handlers()
        if h.file_path is not None
    }
    assert "default_status" in module_stems
    assert "usage_metrics" in module_stems


def test_config_resolver_personal_assistant_session_db_path() -> None:
    """ConfigResolver must resolve session_db_path to ~/.nanoassistant/sessions.sqlite3."""
    resolver = ConfigResolver(profile=PERSONAL_ASSISTANT_PROFILE)
    db_path = resolver.session_db_path()
    assert db_path.name == "sessions.sqlite3"
    # Must be inside ~/.nanoassistant/, not ~/.nanocode/ or any other product dir.
    assert "nanoassistant" in str(db_path)


def test_config_resolver_personal_assistant_global_config_root() -> None:
    """ConfigResolver must resolve global_config_root to expanded ~/.nanoassistant."""
    resolver = ConfigResolver(profile=PERSONAL_ASSISTANT_PROFILE)
    root = resolver.global_config_root()
    assert root.is_absolute()
    assert root.name == ".nanoassistant"


def test_bootstrap_local_coding_regression_tool_ids(tmp_path: Path) -> None:
    """Regression: bootstrap_product(LOCAL_CODING_PROFILE) still returns 5 coding tools."""
    resolved = bootstrap_product(profile=LOCAL_CODING_PROFILE, repo_root=tmp_path)
    assert resolved.tool_registry is not None
    tool_names = {spec.name for spec in resolved.tool_registry.list_specs()}
    assert tool_names == {"read", "write", "edit", "bash", "task"}


def test_bootstrap_local_coding_regression_hook_has_bash_risk_gate(tmp_path: Path) -> None:
    """Regression: LOCAL_CODING_PROFILE bootstrap hook registry must still include bash_risk_gate."""
    resolved = bootstrap_product(profile=LOCAL_CODING_PROFILE, repo_root=tmp_path)
    assert resolved.hook_registry is not None
    module_stems = {
        Path(h.file_path).stem
        for h in resolved.hook_registry.all_handlers()
        if h.file_path is not None
    }
    assert "bash_risk_gate" in module_stems
