import io
import json

from nano_multiagent.apps.coding_cli.main import run_cli


class _ConnectionRefusedOnHealthClient:
    def __enter__(self) -> "_ConnectionRefusedOnHealthClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def health(self) -> dict[str, object]:
        raise ConnectionRefusedError(61, "Connection refused")


def test_cli_single_command_error_payload_contract_contains_layer() -> None:
    output = io.StringIO()
    exit_code = run_cli(
        ["--mode", "remote", "--token", "test-token", "health"],
        stdout=output,
        client_factory=lambda _: (_ for _ in ()).throw(AssertionError("should not build client")),
    )

    assert exit_code == 1
    raw = output.getvalue().strip()
    assert "\n" not in raw
    payload = json.loads(raw)
    assert {"error", "suggestion", "layer"}.issubset(payload.keys())
    assert payload["layer"] == "input"
    assert isinstance(payload["error"], str)
    assert isinstance(payload["suggestion"], str)


def test_cli_single_command_network_error_payload_contract_contains_layer() -> None:
    output = io.StringIO()
    exit_code = run_cli(
        [
            "--mode",
            "remote",
            "--base-url",
            "http://127.0.0.1:8222",
            "--token",
            "test-token",
            "health",
        ],
        stdout=output,
        client_factory=lambda _: _ConnectionRefusedOnHealthClient(),
    )

    assert exit_code == 1
    payload = json.loads(output.getvalue().strip())
    assert {"error", "suggestion", "layer"}.issubset(payload.keys())
    assert payload["layer"] == "network"
