"""Shared fixtures for integration tests.

The HTTP ASGI client helpers (ASGIClient, _IncrementalSseParser) were removed
in refactor-387-M4 together with agent.platform.http_api.  Integration tests
that used ASGIClient were deleted; tests that test kernel behavior directly
should use agent.sdk (build_kernel / Kernel) instead.
"""
