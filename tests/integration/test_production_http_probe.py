"""Exercise the production probe through a real, TLS-verified HTTP CONNECT proxy."""

from __future__ import annotations

import json
import os
import select
import socket
import socketserver
import ssl
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def proxy_probe(tmp_path):
    key, cert = tmp_path / "key.pem", tmp_path / "cert.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=im.nanoim.win",
            "-addext",
            "subjectAltName=DNS:im.nanoim.win",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )

    class Origin(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"production page through configured proxy"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    origin = ThreadingHTTPServer(("127.0.0.1", 0), Origin)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    origin.socket = tls.wrap_socket(origin.socket, server_side=True)
    targets = []

    class Proxy(socketserver.StreamRequestHandler):
        def handle(self):
            method, target, _ = self.rfile.readline().decode().split()
            while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                pass
            assert method == "CONNECT"
            targets.append(target)
            with socket.create_connection(origin.server_address) as upstream:
                self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self.wfile.flush()
                while True:
                    ready, _, _ = select.select([self.connection, upstream], [], [], 5)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        destination = (
                            upstream if source is self.connection else self.connection
                        )
                        destination.sendall(data)

    proxy = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Proxy)
    proxy.daemon_threads = True
    for server in (origin, proxy):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    config = tmp_path / "gateway.yaml"
    proxy_url = f"http://fixture:fixture-password@127.0.0.1:{proxy.server_address[1]}"

    def run(environment, *extra):
        config.write_text(yaml.safe_dump({"gateway": {"environment": environment}}))
        inherited = {
            **os.environ,
            "SSL_CERT_FILE": str(cert),
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
        }
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/prod_tunnel.py"),
                "--public-only",
                "--gateway-config",
                str(config),
                *extra,
            ],
            env=inherited,
            capture_output=True,
            text=True,
            timeout=20,
        )

    try:
        yield run, proxy_url, targets
    finally:
        for server in (origin, proxy):
            server.shutdown()
            server.server_close()


def test_public_probe_uses_persisted_proxy_and_reads_the_complete_tls_response(
    proxy_probe,
):
    run, proxy_url, targets = proxy_probe
    result = run({"HTTPS_PROXY": proxy_url, "NO_PROXY": "127.0.0.1,localhost"})
    assert result.returncode == 0, result.stdout + result.stderr
    snapshot = json.loads(result.stdout)
    assert snapshot["public_egress"] == "configured_proxy"
    assert snapshot["https"] == 200
    assert snapshot["bytes"] > 0
    assert targets == ["im.nanoim.win:443"]
    assert "fixture-password" not in result.stdout + result.stderr


def test_public_probe_rejects_missing_service_proxy_instead_of_using_ambient_proxy(
    proxy_probe,
):
    run, _, targets = proxy_probe
    result = run({})
    assert result.returncode == 1
    assert "requires a configured HTTPS proxy" in result.stdout
    assert targets == []


def test_proxy_failure_is_not_reported_as_a_tunnel_failure_or_retried_directly(
    proxy_probe,
):
    run, _, targets = proxy_probe
    result = run({"HTTPS_PROXY": "http://127.0.0.1:9"})
    assert result.returncode == 1
    assert "Public HTTPS via configured_proxy failed" in result.stdout
    assert "Tunnel" not in result.stdout
    assert targets == []
