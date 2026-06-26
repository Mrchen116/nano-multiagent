"""Unit tests for presentation detail hard cap truncation."""

from agent.platform.tools.presentation import (
    PRESENTATION_DETAIL_HARD_CAP_BYTES,
    _enforce_cap,
)


def test_enforce_cap_no_truncation() -> None:
    detail = {"stdout": "small output", "stderr": ""}
    result = _enforce_cap(detail)
    assert result["stdout"] == "small output"
    assert "truncated" not in result or result.get("truncated") is False


def test_enforce_cap_truncates_stdout() -> None:
    huge = "x" * (PRESENTATION_DETAIL_HARD_CAP_BYTES + 1000)
    detail = {"stdout": huge, "stderr": ""}
    result = _enforce_cap(detail)
    assert result["truncated"] is True
    stdout = result["stdout"]
    assert "[truncated]" in stdout
    assert len(stdout.encode("utf-8")) < PRESENTATION_DETAIL_HARD_CAP_BYTES + 100


def test_enforce_cap_truncates_diff() -> None:
    huge = "y" * (PRESENTATION_DETAIL_HARD_CAP_BYTES + 500)
    detail = {"diff": huge, "path": "src/app.py"}
    result = _enforce_cap(detail)
    assert result["truncated"] is True
    assert "[truncated]" in result["diff"]


def test_enforce_cap_truncates_content() -> None:
    huge = "z" * (PRESENTATION_DETAIL_HARD_CAP_BYTES + 500)
    detail = {"content": huge}
    result = _enforce_cap(detail)
    assert result["truncated"] is True
    assert "[truncated]" in result["content"]


def test_write_start_detail_reuses_content_cap() -> None:
    from agent.platform.tools.builtins.write import WriteTool

    huge = "w" * (PRESENTATION_DETAIL_HARD_CAP_BYTES + 500)
    detail = WriteTool.presenter.format_start(
        {"path": "big.txt", "content": huge}
    ).detail
    assert detail is not None
    assert detail["path"] == "big.txt"
    assert detail["truncated"] is True
    assert "[truncated]" in detail["content"]


def test_memory_start_detail_reuses_content_cap() -> None:
    from agent.platform.tools.builtins.memory import MemoryTool

    huge = "m" * (PRESENTATION_DETAIL_HARD_CAP_BYTES + 500)
    detail = MemoryTool.presenter.format_start(
        {"action": "add", "target": "memory", "content": huge}
    ).detail
    assert detail is not None
    assert detail["action"] == "add"
    assert detail["target"] == "memory"
    assert detail["truncated"] is True
    assert "[truncated]" in detail["content"]


def test_enforce_cap_none_returns_none() -> None:
    assert _enforce_cap({}) == {}
    assert _enforce_cap(None) is None
