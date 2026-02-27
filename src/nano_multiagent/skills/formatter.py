from html import escape
from typing import Sequence

from .registry import SkillMetadata

SKILLS_GUIDANCE = (
    "The following skills provide specialized instructions for specific tasks.\n"
    "Use the read tool to load a skill's file when the task matches its description.\n"
    "When a skill file references a relative path, resolve it against the skill directory "
    "(parent of SKILL.md / dirname of the path) and use that absolute path in tool commands.\n"
    "When a task matches a listed skill, first call read on its <location> before following its instructions."
)


def format_available_skills_section(skills: Sequence[SkillMetadata]) -> str:
    if not skills:
        return ""

    lines = [SKILLS_GUIDANCE, "", "<available_skills>"]
    for skill in skills:
        lines.extend(
            (
                "  <skill>",
                f"    <name>{escape(skill.name)}</name>",
                f"    <description>{escape(skill.description)}</description>",
                f"    <location>{escape(str(skill.location.expanduser().resolve()))}</location>",
                "  </skill>",
            )
        )
    lines.append("</available_skills>")
    return "\n".join(lines)
