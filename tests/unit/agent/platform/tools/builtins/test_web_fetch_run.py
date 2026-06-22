"""Tests for WebFetchTool.run() output shape (feat-425 决策 4).

run() now also returns ``content`` (the display body with the untrusted banner
stripped) and ``final_url`` (post-redirect URL) so the presenter/WebCard renders a
non-empty body and the real landing URL. The LLM-facing ``text`` (with banner) is
unchanged — ``serialize_result`` still reads only ``text``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from agent.core.tools.base import ToolContext
from agent.platform.tools.builtins.web_fetch import WebFetchTool, _UNTRUSTED_BANNER


def _ctx() -> ToolContext:
    ctx = MagicMock(spec=ToolContext)
    ctx.llm_client = None
    return ctx


class _FakeResp:
    def __init__(self, *, status_code: int, text: str, ctype: str, url: str) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": ctype}
        self.url = url


def test_run_returns_content_without_banner() -> None:
    # content 是剥掉 untrusted banner 的展示正文;text 仍带 banner 给模型。
    resp = _FakeResp(
        status_code=200,
        text="<html><body>hello body</body></html>",
        ctype="text/html",
        url="https://example.com/",
    )
    with patch("agent.platform.tools.builtins.web_fetch._do_fetch", return_value=resp):
        out: Any = WebFetchTool().run({"url": "https://example.com"}, _ctx())
    assert out["ok"] is True
    assert out["status"] == 200
    # text 仍带 banner(LLM-facing)
    assert out["text"].startswith(_UNTRUSTED_BANNER)
    # content 不含 banner(展示正文)
    assert "content" in out
    assert _UNTRUSTED_BANNER not in out["content"]
    assert "hello body" in out["content"]


def test_run_returns_final_url() -> None:
    resp = _FakeResp(
        status_code=200,
        text="body",
        ctype="text/plain",
        url="https://example.com/landing",
    )
    with patch("agent.platform.tools.builtins.web_fetch._do_fetch", return_value=resp):
        out: Any = WebFetchTool().run({"url": "https://example.com"}, _ctx())
    assert out["final_url"] == "https://example.com/landing"


def test_run_invalid_url_returns_ok_false() -> None:
    # 非法 URL: run() 返回 {ok:False,error},不抛(失败态由 presenter 判 ok is False)。
    out: Any = WebFetchTool().run({"url": "https://localhost"}, _ctx())
    assert out["ok"] is False
    assert "error" in out


def test_serialize_result_still_reads_text_only() -> None:
    # 回归:serialize_result 只吐 text(带 banner),不受新增 content/final_url 影响。
    tool = WebFetchTool()
    serialized = tool.serialize_result(
        {
            "ok": True,
            "text": f"{_UNTRUSTED_BANNER}\n\nfull text",
            "content": "full text",
            "truncated": False,
        }
    )
    assert serialized == f"{_UNTRUSTED_BANNER}\n\nfull text"
