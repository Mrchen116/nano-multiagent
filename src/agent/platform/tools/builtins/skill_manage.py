"""Built-in `skill_manage` tool: thin platform wrapper over core/skills SkillWriter.

Responsibilities:
- Expose create / edit / patch / view / list actions to the LLM via the Tool protocol.
- Delegate write-side operations to ``SkillWriter``; read-side to ``SkillRegistry``.
- Return structured ``{"success": bool, ...}`` dicts; never raise exceptions from run().
- No security scan (design R6; can be added later).

Architecture: ``platform`` layer — imports ``core/skills`` and ``core/tools``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from agent.core.skills.registry import SkillRegistry
from agent.core.skills.writer import SkillWriter

# Actions supported by this tool (design §4 interface)
_SUPPORTED_ACTIONS = frozenset({"create", "edit", "patch", "view", "list"})


class SkillManageTool:
    """Manage user skills: create, edit, patch, view, and list skill files.

    This tool is used by both the primary agent (when it wants to
    proactively create or update a skill) and the background review agent
    (restricted to this tool plus ``memory`` via the execution-layer allowlist).

    Args:
        skill_root: Directory containing per-skill subdirectories. Injected at
            construction time by bootstrap / wiring layer.
        registry: SkillRegistry instance to use for list/view operations and
            cache invalidation after writes.
    """

    name = "skill_manage"
    is_concurrency_safe = False
    max_result_size_chars = 50_000

    description = (
        "Manage persistent skill files that teach you how to do classes of tasks.\n\n"
        "ACTIONS:\n"
        "- create: Create a new skill (name + content with YAML frontmatter).\n"
        "- edit: Fully replace an existing skill's SKILL.md content.\n"
        "- patch: Apply a find-and-replace to an existing skill (old_string → new_string).\n"
        "- view: Read an existing skill's SKILL.md content by name.\n"
        "- list: List all available skill names and descriptions.\n\n"
        "WHEN TO USE:\n"
        "After completing a complex task (5+ tool calls), fixing a tricky error, or "
        "discovering a non-trivial workflow, save the approach as a skill so you can "
        "reuse it next time. When using a skill and finding it outdated, incomplete, or "
        "wrong, patch it immediately.\n\n"
        "SKILL CONTENT FORMAT:\n"
        "Content must include YAML frontmatter with 'name' and 'description' fields, "
        "followed by markdown body. Example:\n"
        "---\nname: my-skill\ndescription: How to do X\n---\n\n# Instructions\n..."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "edit", "patch", "view", "list"],
                "description": "The action to perform.",
            },
            "name": {
                "type": "string",
                "description": "Skill name (required for create/edit/patch/view).",
            },
            "content": {
                "type": "string",
                "description": "Full SKILL.md content for create/edit actions.",
            },
            "old_string": {
                "type": "string",
                "description": "Unique substring to replace (patch action).",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement string for patch action (may be empty to delete).",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def __init__(self, *, skill_root: Path, registry: SkillRegistry) -> None:
        self._writer = SkillWriter(skill_root=skill_root, registry=registry)
        self._registry = registry

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:
        """Dispatch the requested action; return structured success/error dict."""
        action = str(args.get("action", ""))

        if action not in _SUPPORTED_ACTIONS:
            return {
                "success": False,
                "error": f"Unknown action '{action}'; supported: {sorted(_SUPPORTED_ACTIONS)}",
            }

        try:
            return self._dispatch(action, args)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Unexpected error: {exc}"}

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        """Serialize tool result to a string for the LLM."""
        if error is not None:
            return error
        if isinstance(output, Mapping):
            if not output.get("success", True):
                return f"Error: {output.get('error', 'unknown error')}"
            # Remove success flag from LLM-facing output for clarity
            display = {k: v for k, v in output.items() if k != "success"}
            return json.dumps(display, ensure_ascii=False, indent=2)
        return str(output)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def _dispatch(self, action: str, args: Mapping[str, Any]) -> Mapping[str, Any]:
        if action == "create":
            return self._create(args)
        if action == "edit":
            return self._edit(args)
        if action == "patch":
            return self._patch(args)
        if action == "view":
            return self._view(args)
        if action == "list":
            return self._list()
        raise ValueError(f"Unhandled action '{action}'")  # unreachable

    def _create(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        name = args.get("name")
        content = args.get("content")
        if not name:
            return {"success": False, "error": "create action requires 'name'"}
        if not content:
            return {"success": False, "error": "create action requires 'content'"}
        path = self._writer.create(str(name), str(content))
        return {"success": True, "message": f"created skill '{name}' at {path}"}

    def _edit(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        name = args.get("name")
        content = args.get("content")
        if not name:
            return {"success": False, "error": "edit action requires 'name'"}
        if not content:
            return {"success": False, "error": "edit action requires 'content'"}
        path = self._writer.edit(str(name), str(content))
        return {"success": True, "message": f"updated skill '{name}' at {path}"}

    def _patch(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        name = args.get("name")
        old_string = args.get("old_string")
        new_string = args.get("new_string")
        if not name:
            return {"success": False, "error": "patch action requires 'name'"}
        if old_string is None:
            return {"success": False, "error": "patch action requires 'old_string'"}
        if new_string is None:
            return {"success": False, "error": "patch action requires 'new_string'"}
        path = self._writer.patch(str(name), old_string=str(old_string), new_string=str(new_string))
        return {"success": True, "message": f"patched skill '{name}' at {path}"}

    def _view(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        name = args.get("name")
        if not name:
            return {"success": False, "error": "view action requires 'name'"}
        # Find the skill in the registry
        skills = self._registry.list_skills()
        skill = next((s for s in skills if s.name == str(name)), None)
        if skill is None:
            return {"success": False, "error": f"Skill '{name}' not found"}
        content = skill.location.read_text(encoding="utf-8")
        return {"success": True, "name": str(name), "content": content, "location": str(skill.location)}

    def _list(self) -> Mapping[str, Any]:
        skills = self._registry.list_skills()
        skill_list = [{"name": s.name, "description": s.description} for s in skills]
        return {"success": True, "skills": skill_list, "count": len(skill_list)}
