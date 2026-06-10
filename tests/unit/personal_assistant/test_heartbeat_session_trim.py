"""Tests for feat-394-M1 B: transcript trimming after silent heartbeat ticks.

B condition: after a silent poll (no meaningful work), the heartbeat runner must
truncate the JSONL session file back to the pre-submit line count, eliminating
the heartbeat trigger prompt and ack turn from the session history (net-zero residual).
"""

from __future__ import annotations

import asyncio
from pathlib import Path


# ---------------------------------------------------------------------------
# B — transcript 修剪：静默轮询后会话无噪声
# ---------------------------------------------------------------------------


def test_polling_runner_has_trim_silent_tick_method(tmp_path: Path) -> None:
    """PollingHeartbeatRunner 必须有 trim_silent_tick 方法."""
    from personal_assistant.main import PollingHeartbeatRunner

    assert hasattr(PollingHeartbeatRunner, "trim_silent_tick"), (
        "PollingHeartbeatRunner 缺少 trim_silent_tick 方法"
    )


def test_polling_runner_trims_silent_tick_truncates_jsonl(tmp_path: Path) -> None:
    """PollingHeartbeatRunner.trim_silent_tick 截断 JSONL 到 pre_submit_line_count 行.

    这是 B 条退出标准的核心：静默轮询完成后，JSONL 文件被截断到 run 之前的行数，
    消除 heartbeat 触发 prompt + ack turn（net zero residual）。
    """
    from personal_assistant.main import PollingHeartbeatRunner

    # 准备一个包含 3 行的 JSONL 文件（模拟 run 前的 session 历史）
    session_dir = tmp_path / ".nanoassistant" / "sessions"
    session_dir.mkdir(parents=True)
    session_file = session_dir / "sess-b1.jsonl"
    pre_submit_lines = [
        '{"type":"session_created","session_id":"sess-b1","created_at":"2026-01-01T00:00:00Z"}\n',
        '{"type":"turn","uuid":"msg-1","role":"user","content":"hello","timestamp":"2026-01-01T00:01:00Z"}\n',
        '{"type":"turn","uuid":"msg-2","role":"assistant","content":"hi there","timestamp":"2026-01-01T00:01:01Z"}\n',
    ]
    session_file.write_text("".join(pre_submit_lines), encoding="utf-8")

    # 模拟 heartbeat run 追加了触发 prompt 和 ack turn（2 行）
    with session_file.open("a", encoding="utf-8") as f:
        f.write(
            '{"type":"turn","uuid":"hb-prompt","role":"user","content":"Read HEARTBEAT.md...","timestamp":"2026-01-01T01:00:00Z"}\n'
        )
        f.write(
            '{"type":"turn","uuid":"hb-ok","role":"assistant","content":"HEARTBEAT_OK","timestamp":"2026-01-01T01:00:01Z"}\n'
        )

    assert session_file.read_text(encoding="utf-8").count("\n") == 5, (
        "setup: should be 5 lines"
    )

    runner = PollingHeartbeatRunner.__new__(PollingHeartbeatRunner)

    # trim_silent_tick(session_file, pre_submit_line_count) 应截断到 pre_submit_line_count 行
    asyncio.run(
        runner.trim_silent_tick(
            session_file=session_file,
            pre_submit_line_count=len(pre_submit_lines),
        )
    )

    remaining = session_file.read_text(encoding="utf-8")
    remaining_lines = [l for l in remaining.splitlines() if l.strip()]
    assert len(remaining_lines) == 3, (
        f"截断后应剩 3 行（run 前的历史）；实际剩 {len(remaining_lines)} 行:\n{remaining}"
    )
    assert "HEARTBEAT_OK" not in remaining, (
        "静默 tick 修剪后 HEARTBEAT_OK ack turn 不应残留"
    )
    assert "HEARTBEAT.md" not in remaining, (
        "静默 tick 修剪后 heartbeat 触发 prompt 不应残留"
    )
