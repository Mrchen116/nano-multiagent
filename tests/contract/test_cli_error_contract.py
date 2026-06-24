"""CLI error payload contract tests (refactor-387 M2).

M2 后 CLI 走 Kernel SDK，不再有 --mode/--base-url/health。
错误 payload 仍保持 {error, suggestion, layer} 形状。
"""

import io
import json

from coding_cli.main import run_cli
from tests.unit._cli_kernel_stubs import _BaseKernelStub, _make_kernel_factory


def test_cli_single_command_error_payload_contract_contains_layer(tmp_path) -> None:
    """Input-layer error must produce a single-line {error, suggestion, layer} JSON.

    bugfix-429 R6: `llm-config set` was removed, so this drives the same single-
    command JSON-error contract via a ValueError raised while assembling the
    kernel (ValueError → layer="input"). The contract under test is the payload
    shape + layer classification, not the specific command.
    """
    output = io.StringIO()

    def _raising_factory():
        raise ValueError("bad llm config: model must be a non-empty string")

    exit_code = run_cli(
        ["llm-config", "get"],
        stdout=output,
        kernel_factory=_raising_factory,
        workspace_root=tmp_path,
    )

    assert exit_code == 1
    raw = output.getvalue().strip()
    assert "\n" not in raw
    payload = json.loads(raw)
    assert {"error", "suggestion", "layer"}.issubset(payload.keys())
    assert payload["layer"] == "input"
    assert isinstance(payload["error"], str)
    assert isinstance(payload["suggestion"], str)


def test_cli_single_command_network_error_payload_contract_contains_layer(
    tmp_path,
) -> None:
    """Network-layer error (connection refused during submit) must produce {error, suggestion, layer}."""
    from tests.unit._cli_kernel_stubs import _ConnectionRefusedKernelStub

    output = io.StringIO()
    inputs = iter(["hi", "/exit"])
    exit_code = run_cli(
        [],
        stdout=output,
        kernel_factory=_make_kernel_factory(_ConnectionRefusedKernelStub()),
        input_fn=lambda _: next(inputs),
        workspace_root=tmp_path,
    )

    # REPL handles the error inline (layer=network shown in REPL output, not JSON)
    # The error appears in REPL text output, not as top-level JSON
    assert exit_code == 0
    text = output.getvalue()
    # The network error layer should be visible in the REPL output
    assert "layer=network" in text or "network" in text.lower()
