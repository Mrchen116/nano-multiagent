from pathlib import Path

from personal_assistant import main as personal_assistant_main
from personal_assistant.gateway import composition
from personal_assistant.gateway.runtime import GatewayRuntime


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_personal_assistant_main_entry_exists() -> None:
    assert (REPO_ROOT / "src" / "personal_assistant" / "main.py").is_file()


def test_personal_assistant_main_exports_only_cli_entry() -> None:
    assert personal_assistant_main.__all__ == ["main"]


def test_gateway_composition_exposes_the_only_runtime_factory() -> None:
    assert hasattr(composition, "compose_gateway")
    assert not hasattr(personal_assistant_main, "build_runtime")


def test_gateway_runtime_exports_lifecycle_controls_from_its_owner() -> None:
    assert not hasattr(personal_assistant_main, "GatewayRuntime")
    assert hasattr(GatewayRuntime, "wait_until_ready")
    assert hasattr(GatewayRuntime, "request_shutdown")


def test_personal_assistant_main_does_not_define_relay_lifecycle_callback() -> None:
    source = (REPO_ROOT / "src" / "personal_assistant" / "main.py").read_text()

    assert "def _build_relay_lifecycle_callback(" not in source


def test_personal_assistant_main_uses_lifecycle_owners_by_module() -> None:
    source = (REPO_ROOT / "src" / "personal_assistant" / "main.py").read_text()

    assert "from personal_assistant.gateway.connection_ready import" not in source
    assert "from personal_assistant.gateway.im_bootstrap import" not in source
    assert "from personal_assistant.gateway.process_lifecycle import" not in source
    assert "process_lifecycle.launch_gateway_in_background(" in source
    assert "connection_ready.ConnectionReadyCoordinator(" in source
    assert "im_bootstrap.IMBootstrapClient(" in source


def test_runtime_delivery_observer_keeps_typed_store_owner_at_entry() -> None:
    source = (
        REPO_ROOT
        / "src"
        / "personal_assistant"
        / "gateway"
        / "runtime_delivery"
        / "observer.py"
    ).read_text()

    assert "run_context_store = run_context_store.legacy_contexts" not in source
