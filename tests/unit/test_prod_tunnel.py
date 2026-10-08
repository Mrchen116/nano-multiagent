"""Protect the production exit gate and live-but-unready recovery boundary."""

import importlib.util
import signal
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml


@pytest.fixture
def tunnel(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "prod_tunnel", Path(__file__).parents[2] / "scripts/prod_tunnel.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = tmp_path / "tunnel.yml"
    config.write_text(
        yaml.safe_dump(
            {"protocol": "quic", "edge-ip-version": "6", "metrics": "127.0.0.1:20241"}
        )
    )
    pid = tmp_path / "child.pid"
    pid.write_text("123")
    monkeypatch.setattr(module, "TUNNEL_CONFIG", config)
    monkeypatch.setattr(module, "CHILD_PID", pid)
    state = {
        "interface": "en0",
        "listener": "n127.0.0.1:20241\n",
        "sockets": 4,
        "ha": 4,
        "received": 100,
        "closed": 0,
    }

    def command(args, **kwargs):
        if args[0] == "ps":
            return "/opt/homebrew/bin/cloudflared\n"
        if args[0] == "lsof":
            if "-iTCP:20241" in args:
                return state["listener"]
            return "\n".join(f"n*:{5000 + i}" for i in range(state["sockets"]))
        return f"interface: {state['interface']}\n"

    monkeypatch.setattr(module.subprocess, "check_output", command)
    monkeypatch.setattr(module, "_ready", lambda: True)

    def response(url, **kwargs):
        metrics = f"cloudflared_tunnel_ha_connections {state['ha']}\n"
        metrics += f"quic_client_closed_connections {state['closed']}\n"
        for i in range(4):
            metrics += f'quic_client_sent_bytes{{conn_index="{i}"}} 100\n'
            metrics += (
                f'quic_client_receive_bytes{{conn_index="{i}"}} {state["received"]}\n'
            )
        return httpx.Response(200, text=metrics, request=httpx.Request("GET", url))

    monkeypatch.setattr(module.httpx, "get", response)
    monkeypatch.setattr("sys.argv", ["prod_tunnel.py"])
    return module, state


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "tun",
        "other_pid",
        "wrong_family",
        "no_traffic",
        "missing_ha",
        "tcp",
        "ipv4",
    ],
)
def test_deploy_gate_checks_actual_production_pid_and_ipv6_exit(
    tunnel, failure, capsys
):
    module, state = tunnel
    if failure == "tun":
        state["interface"] = "utun9"
    elif failure == "other_pid":
        state["listener"] = ""
    elif failure == "wrong_family":
        state["sockets"] = 0
    elif failure == "no_traffic":
        state["received"] = 0
    elif failure == "missing_ha":
        state["ha"] = 3
    elif failure in ["tcp", "ipv4"]:
        config = yaml.safe_load(module.TUNNEL_CONFIG.read_text())
        config["protocol" if failure == "tcp" else "edge-ip-version"] = (
            "http2" if failure == "tcp" else "4"
        )
        module.TUNNEL_CONFIG.write_text(yaml.safe_dump(config))
    assert module.main() == (1 if failure else 0)
    assert ("FAIL:" in capsys.readouterr().out) == bool(failure)


def test_continuous_gate_rejects_reconnection_between_samples(tunnel, monkeypatch):
    module, state = tunnel
    clock = [0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def advance(seconds):
        clock[0] += seconds
        state["closed"] += 1

    monkeypatch.setattr(module.time, "sleep", advance)
    monkeypatch.setattr("sys.argv", ["prod_tunnel.py", "--seconds", "20"])
    assert module.main() == 1


def test_supervisor_replaces_live_child_after_sustained_readiness_failure(
    tunnel, monkeypatch
):
    module, _ = tunnel
    clock = [0]
    children = []
    handlers = {}
    monkeypatch.setattr(
        module.signal, "signal", lambda sig, handler: handlers.update({sig: handler})
    )
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    def spawn(_args):
        child = SimpleNamespace(
            pid=123 + len(children), stopped=False, started=clock[0]
        )
        child.poll = lambda: 0 if child.stopped else None
        child.terminate = lambda: setattr(child, "stopped", True)
        child.wait = lambda **kwargs: 0
        children.append(child)
        return child

    def advance(seconds):
        clock[0] += seconds
        if len(children) == 2:
            handlers[signal.SIGTERM](signal.SIGTERM, None)

    monkeypatch.setattr(module.subprocess, "Popen", spawn)
    monkeypatch.setattr(module.time, "sleep", advance)
    monkeypatch.setattr(module, "_ready", lambda: False)
    monkeypatch.setattr("sys.argv", ["prod_tunnel.py", "--supervise"])
    assert module.main() == 0
    assert len(children) == 2
    assert children[0].stopped
    assert (
        module.RECOVERY_SECONDS
        <= children[1].started
        <= module.RECOVERY_SECONDS + 2 * module.POLL_SECONDS
    )
    assert not module.CHILD_PID.exists()
