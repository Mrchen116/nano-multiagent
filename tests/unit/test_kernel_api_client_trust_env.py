"""kernel_api_client trust_env 单元测试。

AsyncClient 在 localhost URL 下必须与同步 Client 一致：不读代理环境变量，
否则 venv 缺 socksio 时 SOCKS_PROXY env 会触发 ImportError，错误文本绕过
bugfix-380 的 _build_provider_error_message 路径直接灌进 IM 气泡。
"""

from __future__ import annotations

import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from personal_assistant.client.kernel_api_client import (
    KernelApiClient,
    KernelApiClientConfig,
)

_ASYNC_CLIENT_PATH = "personal_assistant.client.kernel_api_client.httpx.AsyncClient"
_SYNC_CLIENT_PATH = "personal_assistant.client.kernel_api_client.httpx.Client"

# 必须提供 token，否则 _build_headers(require_auth=True) 在 AsyncClient 调用前就抛 ValueError
_LOCALHOST_CFG = KernelApiClientConfig(base_url="http://127.0.0.1:8000", token="test-token")
_EXTERNAL_CFG = KernelApiClientConfig(base_url="https://api.example.com", token="test-token")


def _make_mock_async_client() -> MagicMock:
    """构造一个可用于 async with / stream 的 AsyncClient mock。"""
    mock_instance = MagicMock()
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=None)

    mock_resp = MagicMock()
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)
    mock_resp.status_code = 200

    async def _fake_aiter_bytes():
        yield b""

    mock_resp.aiter_bytes = _fake_aiter_bytes
    mock_instance.stream = MagicMock(return_value=mock_resp)
    return mock_instance


# ---------------------------------------------------------------------------
# 同步 Client 对照基准
# ---------------------------------------------------------------------------


def test_sync_client_uses_trust_env_false_for_localhost() -> None:
    """同步 Client 对 localhost URL 必须传 trust_env=False（对照基准）。"""
    with patch(_SYNC_CLIENT_PATH) as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        KernelApiClient(config=_LOCALHOST_CFG)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs.get("trust_env") is False, (
            f"同步 Client 应对 localhost 传 trust_env=False，实际: {call_kwargs.get('trust_env')!r}"
        )


def test_sync_client_uses_trust_env_true_for_external_url() -> None:
    """同步 Client 对外部 URL 应传 trust_env=True（对照基准）。"""
    with patch(_SYNC_CLIENT_PATH) as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        KernelApiClient(config=_EXTERNAL_CFG)
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs.get("trust_env") is True, (
            f"同步 Client 外部 URL 应传 trust_env=True，实际: {call_kwargs.get('trust_env')!r}"
        )


# ---------------------------------------------------------------------------
# FIX 1: AsyncClient 必须和同步 Client 行为一致
# ---------------------------------------------------------------------------


async def test_async_client_uses_trust_env_false_for_localhost() -> None:
    """AsyncClient 对 localhost URL 必须传 trust_env=False，不继承 SOCKS/HTTP 代理 env。

    触发场景：HTTPS_PROXY=socks5://... 时 httpx 尝试 import socksio，若 venv 缺包
    则抛 ImportError，绕过 bugfix-380 的错误路径直接以 raw 文本灌进 IM 气泡。
    """
    proxy_env = {"HTTPS_PROXY": "socks5://bad-proxy:1080"}
    mock_instance = _make_mock_async_client()

    with patch.dict(os.environ, proxy_env, clear=False):
        with patch(_ASYNC_CLIENT_PATH, return_value=mock_instance) as mock_async_cls:
            client = KernelApiClient(config=_LOCALHOST_CFG)
            try:
                async for _ in client.stream_session(session_id="test-session"):
                    pass
            except Exception:
                pass

            assert mock_async_cls.called, "stream_session 应该调用了 httpx.AsyncClient"
            call_kwargs = mock_async_cls.call_args.kwargs
            assert call_kwargs.get("trust_env") is False, (
                f"AsyncClient 应对 localhost 传 trust_env=False，实际: {call_kwargs.get('trust_env')!r}\n"
                "缺失时代理 env 被继承，venv 缺 socksio 时抛 ImportError。"
            )


async def test_async_client_uses_trust_env_true_for_external_url() -> None:
    """外部 URL 下 AsyncClient 应传 trust_env=True（与同步 Client 保持一致）。

    必须把 *_proxy 环境变量清掉再跑：KernelApiClient.__init__ 还构造一个未被 mock 的
    sync httpx.Client，若 shell 继承了 socks5://... 之类的代理且 venv 缺 socksio，
    sync Client 构造期就 ImportError，测试与本断言无关地失败。
    """
    proxy_vars = (
        "ALL_PROXY", "HTTPS_PROXY", "HTTP_PROXY", "SOCKS_PROXY",
        "all_proxy", "https_proxy", "http_proxy", "socks_proxy",
    )
    clean_env = {k: v for k, v in os.environ.items() if k not in proxy_vars}
    mock_instance = _make_mock_async_client()

    with patch.dict(os.environ, clean_env, clear=True):
        with patch(_ASYNC_CLIENT_PATH, return_value=mock_instance) as mock_async_cls:
            client = KernelApiClient(config=_EXTERNAL_CFG)
            try:
                async for _ in client.stream_session(session_id="test-session"):
                    pass
            except Exception:
                pass

            assert mock_async_cls.called, "stream_session 应该调用了 httpx.AsyncClient"
            call_kwargs = mock_async_cls.call_args.kwargs
            assert call_kwargs.get("trust_env") is True, (
                f"外部 URL 下 AsyncClient 应传 trust_env=True，实际: {call_kwargs.get('trust_env')!r}"
            )
