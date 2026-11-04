"""Protect transport-specific fleet health and reconnect detection."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "prod_tunnel_health", ROOT / "scripts/prod_tunnel.py"
)
tunnel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tunnel)


@pytest.fixture
def configured_tunnel(tmp_path, monkeypatch):
    config = tmp_path / "tunnel.yml"
    pid = tmp_path / "child.pid"
    pid.write_text("123")
    monkeypatch.setattr(tunnel, "TUNNEL_CONFIG", config)
    monkeypatch.setattr(tunnel, "CHILD_PID", pid)
    state = {
        "protocol": "http2",
        "ports": [5000, 5001, 5002, 5003],
        "route": "en0",
        "zero_receive": False,
    }

    def configure(protocol="http2"):
        state["protocol"] = protocol
        config.write_text(
            yaml.safe_dump(
                {
                    "protocol": protocol,
                    "edge-ip-version": "6",
                    "metrics": "127.0.0.1:20241",
                }
            )
        )

    configure()

    def output(args, **_kwargs):
        if args[0] == "/sbin/route":
            return "interface: " + state["route"]
        if args[0] == "ps":
            return "/opt/homebrew/bin/cloudflared"
        if "-sTCP:LISTEN" in args:
            return "n127.0.0.1:20241\n"
        if "-i6TCP" in args:
            assert "-sTCP:ESTABLISHED" in args
            # Local origin/metrics sockets must not masquerade as edge sockets.
            return "\n".join(
                [f"n[2001:db8::1]:{p}->[2606:4700:a0::1]:7844" for p in state["ports"]]
                + ["n[::1]:5500->[::1]:51129"]
            )
        assert "-i6UDP" in args
        return "\n".join(f"n[::]:{p}" for p in state["ports"])

    def metrics(*_args, **_kwargs):
        lines = ["cloudflared_tunnel_ha_connections 4"]
        if state["protocol"] == "quic":
            lines.append("quic_client_closed_connections 7")
            for i in range(4):
                lines += [
                    f'quic_client_sent_bytes{{conn_index="{i}"}} 100',
                    f'quic_client_receive_bytes{{conn_index="{i}"}} {0 if state["zero_receive"] else 100}',
                ]
        response = SimpleNamespace(text="\n".join(lines) + "\n")
        response.raise_for_status = lambda: response
        return response

    monkeypatch.setattr(tunnel.subprocess, "check_output", output)
    monkeypatch.setattr(tunnel.httpx, "get", metrics)
    monkeypatch.setattr(tunnel, "_ready", lambda: True)
    monkeypatch.setattr(tunnel, "public_probe", lambda: {"https": 200, "bytes": 50})
    return state, configure


@pytest.mark.parametrize("protocol", ["quic", "http2"])
def test_accepts_explicit_transport_but_keeps_en0_route_guard(
    configured_tunnel, protocol
):
    state, configure = configured_tunnel
    configure(protocol)
    assert tunnel._check_path() == protocol
    state["route"] = "utun3"
    with pytest.raises(RuntimeError, match="en0"):
        tunnel._check_path()


def test_automatic_fallback_is_not_an_explicit_verified_transport(configured_tunnel):
    _, configure = configured_tunnel
    configure("auto")
    with pytest.raises(RuntimeError, match="explicit"):
        tunnel._check_path()


def test_http2_requires_four_edge_tcp_connections_without_quic_metrics(
    configured_tunnel,
):
    state, _ = configured_tunnel
    snapshot = tunnel._snapshot()
    assert snapshot["ha_connections"] == 4
    assert snapshot["protocol"] == "http2"
    assert snapshot["closed_connections"] is None
    state["ports"].pop()
    with pytest.raises(RuntimeError, match="four IPv6 HTTP2 edge sockets"):
        tunnel._snapshot()


def test_http2_reconnection_fails_gate_even_when_pid_and_ha_recover(
    configured_tunnel, monkeypatch, capsys
):
    state, _ = configured_tunnel
    first = tunnel._snapshot()
    state["ports"][0] += 100
    second = tunnel._snapshot()
    assert first["pid"] == second["pid"]
    assert first["ha_connections"] == second["ha_connections"]
    snapshots = iter([first, second])
    monkeypatch.setattr(tunnel, "_snapshot", lambda: next(snapshots))
    monkeypatch.setattr(tunnel, "configure_business_proxy", lambda _path: None)
    monkeypatch.setattr(tunnel.time, "monotonic", lambda: 0)
    monkeypatch.setattr(tunnel.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sys, "argv", ["prod_tunnel.py", "--seconds", "1"])
    assert tunnel.main() == 1
    assert "changed an edge connection" in capsys.readouterr().out


def test_quic_retains_bidirectional_traffic_and_close_counter_checks(configured_tunnel):
    state, configure = configured_tunnel
    configure("quic")
    assert tunnel._snapshot()["closed_connections"] == 7
    state["zero_receive"] = True
    with pytest.raises(RuntimeError, match="bidirectional"):
        tunnel._snapshot()
