from __future__ import annotations

import json
from pathlib import Path

from agent.core.skills.curator import apply_curator_transitions, run_curator_scan
from agent.core.skills.registry import SkillRegistry


def _write_skill(skill_root: Path, name: str) -> Path:
    skill_file = skill_root / name / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text(
        f"---\nname: {name}\ndescription: {name}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_file


def _write_usage(skill_root: Path, payload: dict[str, object]) -> None:
    skill_root.mkdir(parents=True, exist_ok=True)
    (skill_root / ".usage.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _read_usage(skill_root: Path) -> dict[str, object]:
    return json.loads((skill_root / ".usage.json").read_text(encoding="utf-8"))


def test_curator_marks_f3_f4_skills_stale_after_30_idle_days(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "auto-skill")
    _write_usage(
        skill_root,
        {
            "auto-skill": {
                "source": "F3",
                "state": "active",
                "created_at": "2026-03-01T00:00:00Z",
                "last_used_at": "2026-05-01T00:00:00Z",
            }
        },
    )

    result = run_curator_scan(
        skill_root=skill_root,
        now_iso="2026-06-01T00:00:00Z",
        force=True,
    )
    apply_curator_transitions(result)

    usage = _read_usage(skill_root)
    assert usage["auto-skill"]["state"] == "stale"
    assert (skill_root / "auto-skill" / "SKILL.md").exists()


def test_curator_archives_auto_skills_after_90_idle_days(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "old-auto-skill")
    _write_usage(
        skill_root,
        {
            "old-auto-skill": {
                "source": "F4",
                "state": "stale",
                "created_at": "2026-01-01T00:00:00Z",
                "last_used_at": "2026-02-01T00:00:00Z",
            }
        },
    )

    result = run_curator_scan(
        skill_root=skill_root,
        now_iso="2026-05-05T00:00:00Z",
        force=True,
    )
    apply_curator_transitions(result)

    usage = _read_usage(skill_root)
    assert usage["old-auto-skill"]["state"] == "archived"
    assert usage["old-auto-skill"]["archived_at"] == "2026-05-05T00:00:00Z"
    assert not (skill_root / "old-auto-skill").exists()
    assert (skill_root / ".archive" / "old-auto-skill" / "SKILL.md").exists()


def test_curator_does_not_flow_manual_or_unknown_skills(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    for name in ("f1-skill", "f2-skill", "unknown-skill"):
        _write_skill(skill_root, name)
    _write_usage(
        skill_root,
        {
            "f1-skill": {
                "source": "F1",
                "state": "active",
                "created_at": "2026-01-01T00:00:00Z",
                "last_used_at": "2026-01-01T00:00:00Z",
            },
            "f2-skill": {
                "source": "F2",
                "state": "active",
                "created_at": "2026-01-01T00:00:00Z",
                "last_used_at": "2026-01-01T00:00:00Z",
            },
            "unknown-skill": {
                "source": "unknown",
                "state": "active",
                "created_at": "2026-01-01T00:00:00Z",
                "last_used_at": "2026-01-01T00:00:00Z",
            },
        },
    )

    result = run_curator_scan(
        skill_root=skill_root,
        now_iso="2026-06-01T00:00:00Z",
        force=True,
    )
    apply_curator_transitions(result)

    usage = _read_usage(skill_root)
    assert usage["f1-skill"]["state"] == "active"
    assert usage["f2-skill"]["state"] == "active"
    assert usage["unknown-skill"]["state"] == "active"


def test_curator_reactivates_stale_skill_with_recent_activity(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "revived-skill")
    _write_usage(
        skill_root,
        {
            "revived-skill": {
                "source": "F3",
                "state": "stale",
                "created_at": "2026-01-01T00:00:00Z",
                "last_used_at": "2026-05-25T00:00:00Z",
            }
        },
    )

    result = run_curator_scan(
        skill_root=skill_root,
        now_iso="2026-06-01T00:00:00Z",
        force=True,
    )
    apply_curator_transitions(result)

    usage = _read_usage(skill_root)
    assert usage["revived-skill"]["state"] == "active"


def test_archived_skills_are_not_discovered_by_default(tmp_path: Path) -> None:
    skill_root = tmp_path / "skills"
    _write_skill(skill_root, "visible-skill")
    _write_skill(skill_root / ".archive", "archived-skill")

    skills = SkillRegistry(search_roots=(skill_root,)).list_skills(refresh=True)

    assert [skill.name for skill in skills] == ["visible-skill"]
