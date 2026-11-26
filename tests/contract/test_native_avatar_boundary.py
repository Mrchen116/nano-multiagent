"""Real iOS identities use AvatarView. Preset previews belong to creation and onboarding."""
import re
from pathlib import Path

NATIVE = Path(__file__).resolve().parents[2] / "src/IM/ios/NanoIM"
PREVIEW_SCREENS = {
    "Features/Agents/AgentsView.swift",
    "Features/Agents/PersonalAssistantSetup.swift",
    "Features/Auth/AuthView.swift",
    "Features/Chat/ChatListView.swift",
    "Features/Me/MeView.swift",
}


def test_native_identity_screens_cannot_draw_portrait_presets():
    forbidden = []
    for file in (NATIVE / "Features").rglob("*.swift"):
        source = file.read_text()
        path = file.relative_to(NATIVE).as_posix()
        if re.search(r'Image\(\s*"portrait-|\bAssistantPortrait\s*\(', source):
            forbidden.append(path)
        if path not in PREVIEW_SCREENS and re.search(r"\bPortraitPreview\s*\(", source):
            forbidden.append(path)
    assert not forbidden, f"Use AvatarView(id:size:) for existing identities: {forbidden}"
