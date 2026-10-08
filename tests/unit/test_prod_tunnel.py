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
    config.write_text(yaml.safe_dump({"protocol": "quic", "edge-ip-version": "4"}))
    pid = tmp_path / "child.pid"
    pid.write_text("123")
    monkeypatch.setattr(module, "TUNNEL_CONFIG", config)
    monkeypatch.setattr(module, "CHILD_PID", pid)
    state = {
        "tun": {
            "enable": True,
            "auto-route": True,
            "route-address": module.NETWORKS,
            "device": "utun9",
        },
        "rules": [
            {"type": "IPCIDR", "payload": n, "proxy": module.NODE}
            for n in module.NETWORKS
        ],
        "connections": [
            {
                "metadata": {
                    "network": "udp",
                    "destinationPort": "7844",
                    "sourcePort": str(5000 + i),
                },
                "chains": [module.NODE],
                "download": 100,
            }
            for i in range(4)
        ],
    }

    def api(request):
        value = {
            "/configs": {"tun": state["tun"]},
            "/rules": {"rules": state["rules"]},
            "/connections": {"connections": state["connections"]},
        }
        return httpx.Response(200, json=value[request.url.path])

    monkeypatch.setattr(
        module,
        "_proxy_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(api), base_url="http://localhost"
        ),
    )

    def command(args, **kwargs):
        if args[0] == "ps":
            return "/opt/homebrew/bin/cloudflared\n"
        if args[0] == "lsof":
            return "\n".join(f"n*:{5000 + i}" for i in range(4))
        return "interface: utun9\n"

    monkeypatch.setattr(module.subprocess, "check_output", command)
    monkeypatch.setattr(module, "_ready", lambda: True)
    monkeypatch.setattr(
        module.httpx,
        "get",
        lambda url, **kwargs: httpx.Response(
            200,
            text="cloudflared_tunnel_ha_connections 4\n",
            request=httpx.Request("GET", url),
        ),
    )
    monkeypatch.setattr("sys.argv", ["prod_tunnel.py"])
    return module, state


@pytest.mark.parametrize("failure", [None, "direct", "other_pid", "wrong_node"])
def test_deploy_gate_checks_actual_production_pid_and_fixed_exit(
    tunnel, failure, capsys
):
    module, state = tunnel
    if failure == "direct":
        state["rules"][0]["proxy"] = "DIRECT"
    elif failure == "other_pid":
        for flow in state["connections"]:
            flow["metadata"]["sourcePort"] = "9999"
    elif failure == "wrong_node":
        state["connections"][0]["chains"] = ["different proxy"]
    assert module.main() == (1 if failure else 0)
    assert ("FAIL:" in capsys.readouterr().out) == bool(failure)


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
