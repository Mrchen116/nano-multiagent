"""Runtime ownership tests for the Gateway internal dispatch listener."""

from __future__ import annotations

import socket

import httpx

from personal_assistant.gateway.internal_dispatch import InternalDispatchHandler
from personal_assistant.gateway.runtime import GatewayRuntime

from ._gateway_runtime_test_utils import make_config, run_in_thread


def test_two_gateway_runtimes_publish_distinct_actual_dispatch_urls(tmp_path) -> None:
    """Ephemeral listeners let independent Gateway processes coexist."""

    from personal_assistant.gateway.internal_dispatch import InternalDispatchEndpoint

    endpoints = (InternalDispatchEndpoint(), InternalDispatchEndpoint())
    roots = tuple(tmp_path / f"runtime-{index}" for index in range(2))
    for root in roots:
        root.mkdir()
    runtimes = tuple(
        GatewayRuntime(
            make_config(roots[index]),
            internal_dispatch_handler=InternalDispatchHandler(),
            internal_dispatch_endpoint=endpoint,
            gateway_internal_port=0,
        )
        for index, endpoint in enumerate(endpoints)
    )
    running = tuple(run_in_thread(runtime) for runtime in runtimes)
    try:
        assert all(runtime.wait_until_ready(2) for runtime in runtimes)
        urls = tuple(endpoint.current_url() for endpoint in endpoints)
        assert all(url is not None for url in urls)
        assert urls[0] != urls[1]
        for url in urls:
            response = httpx.post(url, json={"text": "hello", "to": "agent-b"})
            assert response.status_code == 503
    finally:
        for runtime in runtimes:
            runtime.request_shutdown()
        for thread, _outcome in running:
            thread.join(timeout=2)


def test_listener_bind_failure_never_reports_runtime_ready(tmp_path) -> None:
    """A real bind conflict is a startup failure, not a degraded ready state."""

    occupied = socket.socket()
    occupied.bind(("127.0.0.1", 0))
    occupied.listen()
    port = occupied.getsockname()[1]
    runtime = GatewayRuntime(
        make_config(tmp_path),
        internal_dispatch_handler=InternalDispatchHandler(),
        gateway_internal_port=port,
    )
    thread, outcome = run_in_thread(runtime)
    try:
        thread.join(timeout=1)
        observed_ready = runtime.wait_until_ready(0)
        if thread.is_alive():
            runtime.request_shutdown()
            thread.join(timeout=2)
    finally:
        occupied.close()

    assert observed_ready is False
    assert isinstance(outcome.get("error"), OSError)
