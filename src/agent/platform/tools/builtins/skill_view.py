"""Built-in `skill_view` tool: read-side skill inspection with usage tracking."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from agent.core.skills.registry import SkillRegistry
from agent.core.skills.root_resolver import resolve_skill_roots
from agent.core.skills.usage import (
    bump_skill_usage,
    reset_uses_since_last_batch,
    source_from_metadata,
)
from agent.platform.tools.presentation import ToolPresentationEvent, _enforce_cap


class _SkillViewPresenter:
    """Presenter for auditable skill_view calls."""

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        name = str(args.get("name", ""))
        return ToolPresentationEvent(
            visible=True,
            label="Skill",
            summary=f"查看 skill：{name}" if name else "查看 skill",
            detail={"name": name},
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        name = str(args.get("name", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            return ToolPresentationEvent(
                visible=True,
                label="Skill",
                summary=f"查看 skill：{name}" if name else "查看 skill",
                detail={"success": False, "error": {"message": str(error)}},
            )
        if isinstance(output, Mapping) and not output.get("success", True):
            return ToolPresentationEvent(
                visible=True,
                label="Skill",
                summary=f"查看 skill：{name}" if name else "查看 skill",
                detail={
                    "success": False,
                    "name": output.get("name", name),
                    "message": str(output.get("error", "")),
                },
            )
        content = str(output.get("content", "")) if isinstance(output, Mapping) else ""
        detail = _enforce_cap(
            {
                "success": True,
                "name": str(output.get("name", name))
                if isinstance(output, Mapping)
                else name,
                "location": str(output.get("location", ""))
                if isinstance(output, Mapping)
                else "",
                "content_preview": content[:1200],
                "content": content,
            }
        )
        return ToolPresentationEvent(
            visible=True,
            label="Skill",
            summary=f"查看 skill：{detail['name']}",
            detail=detail,
        )


_SKILL_VIEW_PRESENTER = _SkillViewPresenter()


class SkillViewTool:
    """Load a skill's SKILL.md content by name."""

    name = "skill_view"
    is_concurrency_safe = False
    max_result_size_chars = 50_000
    presenter = _SKILL_VIEW_PRESENTER

    description = (
        "Load a skill's full SKILL.md content by name. Use this before following "
        "a skill so usage can be audited and preserved across compaction."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The skill name to view.",
            }
        },
        "required": ["name"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        skill_root: Path | None = None,
        registry: SkillRegistry | None = None,
        workspace_config_dirname: str | None = None,
        extra_roots: tuple[Path, ...] = (),
        pa_skill_root: Path | None = None,
    ) -> None:
        self._workspace_config_dirname = workspace_config_dirname
        self._extra_roots = tuple(extra_roots)
        self._pa_skill_root = pa_skill_root
        if skill_root is not None and registry is not None:
            self._fixed_skill_root = skill_root.expanduser().resolve()
            self._fixed_registry: SkillRegistry | None = registry
        else:
            self._fixed_skill_root = None
            self._fixed_registry = None
        if self._fixed_registry is None and not self._workspace_config_dirname:
            raise ValueError(
                "SkillViewTool requires either (skill_root + registry) or "
                "workspace_config_dirname for per-session resolution"
            )

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:
        """Load a visible skill by name and record successful use."""
        name = str(args.get("name", "")).strip()
        if not name:
            return {"success": False, "error": "skill_view requires 'name'"}
        try:
            skill_root, registry = self._resolve_skill_root_registry(ctx)
            skills = registry.list_skills()
            skill = next((item for item in skills if item.name == name), None)
            if skill is None:
                return {"success": False, "name": name, "error": f"Skill '{name}' not found"}
            content = skill.location.read_text(encoding="utf-8")
            metadata = dict(getattr(ctx, "session_metadata", {}) or {})
            usage_result = bump_skill_usage(
                skill_root=skill_root,
                skill_name=name,
                session_id=getattr(ctx, "session_id", None),
                tool_call_id=getattr(ctx, "tool_call_id", None),
                source=source_from_metadata(metadata),
                location=skill.location,
            )
            if usage_result.trigger is not None and self._enqueue_skill_batch_review(
                ctx, usage_result.trigger
            ):
                reset_uses_since_last_batch(skill_root=skill_root, skill_name=name)
            self._register_invoked_skill(ctx, name=name, location=skill.location, root=skill_root)
            return {
                "success": True,
                "name": name,
                "content": content,
                "location": str(skill.location),
            }
        except ValueError as exc:
            return {"success": False, "name": name, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "name": name, "error": f"Unexpected error: {exc}"}

    def serialize_result(self, output: Any, error: str | None = None) -> str:
        """Serialize tool result to a string for the LLM."""
        if error is not None:
            return error
        if isinstance(output, Mapping):
            if not output.get("success", True):
                return f"Error: {output.get('error', 'unknown error')}"
            display = {k: v for k, v in output.items() if k != "success"}
            return json.dumps(display, ensure_ascii=False, indent=2)
        return str(output)

    def _resolve_skill_root_registry(self, ctx: Any) -> tuple[Path, SkillRegistry]:
        if self._fixed_skill_root is not None and self._fixed_registry is not None:
            return self._fixed_skill_root, self._fixed_registry
        resolved = resolve_skill_roots(
            ctx,
            workspace_config_dirname=self._workspace_config_dirname,
            extra_roots=self._extra_roots,
            pa_skill_root=self._pa_skill_root,
        )
        return resolved.agent_skill_root, resolved.registry

    def _register_invoked_skill(
        self, ctx: Any, *, name: str, location: Path, root: Path
    ) -> None:
        register = getattr(ctx, "register_invoked_skill", None)
        if callable(register):
            register(name=name, location=str(location), root_id=str(root))

    def _enqueue_skill_batch_review(self, ctx: Any, trigger: Any) -> bool:
        enqueue = getattr(ctx, "skill_batch_review_enqueue", None)
        if not callable(enqueue):
            return False
        return bool(enqueue(trigger))


__all__ = ["SkillViewTool"]
