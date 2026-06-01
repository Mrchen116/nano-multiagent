import io
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from coding_cli.render.repl_live import ReplBlockRenderer
from coding_cli.render.repl_live import ReplLiveRenderer


@pytest.fixture
def mock_rich():
    with patch("coding_cli.render.repl_live._rich_available", return_value=True):
        with patch("rich.console.Console") as mock_console_cls:
            with patch("rich.live.Live") as mock_live_cls:
                with patch("rich.spinner.Spinner") as mock_spinner_cls:
                    with patch("rich.text.Text") as mock_text_cls:
                        yield {
                            "Console": mock_console_cls,
                            "Live": mock_live_cls,
                            "Spinner": mock_spinner_cls,
                            "Text": mock_text_cls,
                        }


def test_live_renderer_starts_with_spinner(mock_rich) -> None:
    out = io.StringIO()
    renderer = ReplLiveRenderer(out=out)
    mock_live = MagicMock()
    mock_rich["Live"].return_value = mock_live

    with renderer:
        mock_live.start.assert_called_once()
        spinner_call = mock_rich["Spinner"].call_args
        assert spinner_call[0][0] == "dots"
        assert "Thinking..." in spinner_call[1]["text"]

    mock_live.stop.assert_called_once()


def test_on_text_delta_disables_spinner_and_accumulates(mock_rich) -> None:
    out = io.StringIO()
    renderer = ReplLiveRenderer(out=out)
    mock_live = MagicMock()
    mock_rich["Live"].return_value = mock_live

    with renderer:
        renderer.on_text_delta("hello")
        assert renderer._spinner_active is False
        assert renderer._assistant_text == "hello"
        renderer.on_text_delta(" world")
        assert renderer._assistant_text == "hello world"

    text = out.getvalue()
    assert text == ""


def test_on_tool_event_tracks_running_and_done(mock_rich) -> None:
    out = io.StringIO()
    renderer = ReplLiveRenderer(out=out)
    mock_live = MagicMock()
    mock_rich["Live"].return_value = mock_live

    with renderer:
        renderer.on_tool_event("tool_start", {"name": "bash", "call_id": "c1"})
        assert renderer._tool_lines["bash::c1"] == "▸ Tool: bash"
        assert renderer._spinner_active is False

        renderer.on_tool_event(
            "tool_exec_exit", {"name": "bash", "call_id": "c1", "duration_ms": 150}
        )
        assert renderer._tool_lines["bash::c1"] == "✓ Tool: bash (elapsed=150ms)"


def test_on_tool_event_ignores_hidden_events(mock_rich) -> None:
    out = io.StringIO()
    renderer = ReplLiveRenderer(out=out)
    mock_live = MagicMock()
    mock_rich["Live"].return_value = mock_live

    with renderer:
        renderer.on_tool_event("tool_exec_started", {"name": "bash", "call_id": "c1"})
        renderer.on_tool_event("tool_exec_running", {"name": "bash", "call_id": "c1"})
        renderer.on_tool_event("tool_exec_chunk", {"name": "bash", "call_id": "c1"})
        assert "bash::c1" not in renderer._tool_lines


def test_refresh_updates_live_with_text_and_tools(mock_rich) -> None:
    out = io.StringIO()
    renderer = ReplLiveRenderer(out=out)
    mock_live = MagicMock()
    mock_rich["Live"].return_value = mock_live
    mock_text = mock_rich["Text"]

    with renderer:
        renderer.on_text_delta("line1\nline2")
        renderer.on_tool_event("tool_start", {"name": "bash", "call_id": "c1"})

    join_calls = [call for call in mock_text.method_calls if "join" in str(call)]
    assert mock_live.update.called
    # Verify refresh=True is passed so Live actually renders intermediate frames.
    assert any(
        call.kwargs.get("refresh") is True for call in mock_live.update.call_args_list
    )


def test_refresh_shows_spinner_when_empty(mock_rich) -> None:
    out = io.StringIO()
    renderer = ReplLiveRenderer(out=out)
    mock_live = MagicMock()
    mock_rich["Live"].return_value = mock_live

    with renderer:
        pass

    spinner_call = mock_rich["Spinner"].call_args
    assert spinner_call[0][0] == "dots"


def test_non_tty_graceful_degradation() -> None:
    out = io.StringIO()
    with patch("coding_cli.render.repl_live._rich_available", return_value=False):
        renderer = ReplLiveRenderer(out=out)
        with renderer:
            renderer.on_text_delta("hello")
            renderer.on_tool_event("tool_start", {"name": "bash", "call_id": "c1"})

    text = out.getvalue()
    assert text == ""
    assert renderer._live is None


def test_block_renderer_merges_cumulative_text_and_tool_state() -> None:
    emitted: list[str] = []
    renderer = ReplBlockRenderer(emit=emitted.append)

    renderer.on_text_delta("你好")
    renderer.on_tool_event("tool_start", {"name": "bash", "call_id": "c1"})
    renderer.on_text_delta("你好\n第二行")
    renderer.on_tool_event(
        "tool_exec_exit", {"name": "bash", "call_id": "c1", "duration_ms": 12}
    )

    assert emitted == [
        "> 你好",
        "> 你好\n▸ Tool: bash",
        "> 你好\n> 第二行\n▸ Tool: bash",
        "> 你好\n> 第二行\n✓ Tool: bash (elapsed=12ms)",
    ]


def test_block_renderer_skips_duplicate_refreshes() -> None:
    emitted: list[str] = []
    renderer = ReplBlockRenderer(emit=emitted.append)

    renderer.on_text_delta("hello")
    renderer.on_text_delta("hello")
    renderer.on_tool_event("tool_start", {"name": "bash", "call_id": "c1"})
    renderer.on_tool_event("tool_start", {"name": "bash", "call_id": "c1"})

    assert emitted == [
        "> hello",
        "> hello\n▸ Tool: bash",
    ]
