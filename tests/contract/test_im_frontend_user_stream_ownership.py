from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "src" / "IM" / "frontend" / "src"
RUNTIME_ROOT = FRONTEND_SRC / "realtime" / "user-stream"


def _production_typescript() -> list[Path]:
    return [
        path
        for path in FRONTEND_SRC.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        and ".test." not in path.name
        and not path.is_relative_to(RUNTIME_ROOT)
    ]


def test_user_stream_socket_has_one_production_lifecycle_owner() -> None:
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in _production_typescript()
        if "/im/ws/user" in path.read_text(encoding="utf-8")
        or "new WebSocket(" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []
    runtime_source = "\n".join(path.read_text(encoding="utf-8") for path in RUNTIME_ROOT.glob("*.ts"))
    assert runtime_source.count("new WebSocket(") == 1
    assert 'new URL("/im/ws/user"' in runtime_source


def test_realtime_consumers_do_not_import_legacy_streams() -> None:
    forbidden = ("attachUserConversationStream", "openChatStream", "streamConversationEvents")
    offenders: dict[str, list[str]] = {}
    for path in _production_typescript():
        source = path.read_text(encoding="utf-8")
        matches = [symbol for symbol in forbidden if symbol in source]
        if matches:
            offenders[str(path.relative_to(REPO_ROOT))] = matches

    assert offenders == {}
