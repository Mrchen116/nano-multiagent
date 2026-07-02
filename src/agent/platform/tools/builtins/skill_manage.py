"""Built-in `skill_manage` tool: thin platform wrapper over core/skills SkillWriter.

Responsibilities:
- Expose create / edit / patch / list actions to the LLM via the Tool protocol.
- Delegate write-side operations to ``SkillWriter``; list-side to ``SkillRegistry``.
- Return structured ``{"success": bool, ...}`` dicts; never raise exceptions from run().
- No security scan (design R6; can be added later).

Architecture: ``platform`` layer — imports ``core/skills`` and ``core/tools``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from agent.core.skills.registry import SkillRegistry
from agent.core.skills.root_resolver import ResolvedSkillRoots, resolve_skill_roots
from agent.core.skills.usage import ensure_skill_record, source_from_metadata
from agent.core.skills.writer import SkillWriter
from agent.platform.tools.presentation import (
    ToolPresentationEvent,
    _enforce_cap,
    _summarize_skill,
)

# Actions supported by this tool (design §4 interface)
_SUPPORTED_ACTIONS = frozenset(
    {"create", "edit", "patch", "list", "write_file", "remove_file"}
)


# ---------------------------------------------------------------------------
# Presenter (feat-425 决策 3: presentation travels with the tool — class here)
# ---------------------------------------------------------------------------


class _SkillManagePresenter:
    """Presenter for the `skill_manage` tool.

    Result varies by action (create/edit/patch → ``{message}``; list → ``{skills}``).
    Detail surfaces ``action`` / ``name`` (args)
    plus the result message and best-effort path, so the human sees which skill was
    touched instead of truncated JSON.
    """

    def format_start(self, args: Mapping[str, Any]) -> ToolPresentationEvent:
        action = str(args.get("action", ""))
        name = str(args.get("name", ""))
        return ToolPresentationEvent(
            visible=True,
            label="Skill",
            summary=f"{action} {name}".strip(),
            detail={"action": action, "name": name},
        )

    def format_end(
        self,
        args: Mapping[str, Any],
        result: Any,
        duration_ms: int,
    ) -> ToolPresentationEvent:
        action = str(args.get("action", ""))
        name = str(args.get("name", ""))
        output = getattr(result, "output", None) or {}
        error = getattr(result, "error", None)
        if error:
            # feat-409 failalign: 失败态 summary = 干净主参数(人话 skill 摘要),不含 error。
            return ToolPresentationEvent(
                visible=True,
                label="Skill",
                summary=_summarize_skill(action, name) or "failed",
                detail={"error": {"message": str(error)}},
            )
        success = (
            bool(output.get("success", True)) if isinstance(output, Mapping) else True
        )
        message = str(output.get("message", "")) if isinstance(output, Mapping) else ""
        # list returns skills; write actions return the path/message when available.
        path = str(output.get("location", "")) if isinstance(output, Mapping) else ""
        if not success:
            err = str(output.get("error", "")) if isinstance(output, Mapping) else ""
            # feat-409 failalign: success=False 失败态 summary = 干净主参数(人话 skill
            # 摘要),不含 error 文本;error 进 detail.message 供 SkillCard 渲染一次。
            return ToolPresentationEvent(
                visible=True,
                label="Skill",
                summary=_summarize_skill(action, name) or "failed",
                detail={
                    "action": action,
                    "name": name,
                    "message": err,
                    "path": path,
                    "success": False,
                },
            )
        detail = _enforce_cap(
            {
                "action": action,
                "name": name,
                "message": message,
                "path": path,
                "content": str(output.get("content", ""))
                if isinstance(output, Mapping)
                else "",
                "success": True,
            }
        )
        return ToolPresentationEvent(
            visible=True,
            label="Skill",
            # feat-409 protoalign: 折叠 summary 对齐原型 `创建 skill：log-cleanup`
            # —— 中文动作 + skill 名,而非裸 `create log-cleanup`。
            summary=_summarize_skill(action, name) or message,
            detail=detail,
        )


_SKILL_MANAGE_PRESENTER = _SkillManagePresenter()


class SkillManageTool:
    """Manage user skills: create, edit, patch, list, and support files.

    This tool is used by both the primary agent (when it wants to
    proactively create or update a skill) and the background review agent
    (restricted to this tool plus ``memory`` via the execution-layer allowlist).

    Args:
        skill_root: Directory containing per-skill subdirectories. Injected at
            construction time by bootstrap / wiring layer.
        registry: SkillRegistry instance to use for list operations and
            cache invalidation after writes.
    """

    name = "skill_manage"
    is_concurrency_safe = False
    max_result_size_chars = 50_000
    presenter = (
        _SKILL_MANAGE_PRESENTER  # 决策 12: presentation travels with the tool object
    )

    description = (
        "Manage persistent skill files that teach you how to do classes of tasks.\n\n"
        "ACTIONS:\n"
        "- create: Create a new skill (name + content with YAML frontmatter). "
        "Optional scope='agent'|'pa' controls the write root.\n"
        "- edit: Fully replace an existing skill's SKILL.md content.\n"
        "- patch: Apply a find-and-replace to an existing skill (old_string → new_string).\n"
        "- list: List all available skill names and descriptions.\n"
        "- write_file: Add/overwrite a support file under a skill, turning it into a "
        "class-level umbrella. file_path must start with references/ (session detail, "
        "condensed knowledge banks), templates/ (copy-and-modify starters), scripts/ "
        "(re-runnable actions), or assets/.\n"
        "- remove_file: Delete a support file from a skill by file_path.\n\n"
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
                "enum": [
                    "create",
                    "edit",
                    "patch",
                    "list",
                    "write_file",
                    "remove_file",
                ],
                "description": "The action to perform.",
            },
            "name": {
                "type": "string",
                "description": "Skill name (required for create/edit/patch/write_file/remove_file).",
            },
            "content": {
                "type": "string",
                "description": "Full SKILL.md content for create/edit actions.",
            },
            "scope": {
                "type": "string",
                "enum": ["agent", "pa"],
                "description": "Create destination scope; only applies to create. Defaults to agent.",
            },
            "old_string": {
                "type": "string",
                "description": "Unique substring to replace (patch action).",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement string for patch action (may be empty to delete).",
            },
            "file_path": {
                "type": "string",
                "description": (
                    "Support-file path relative to the skill dir for write_file/remove_file; "
                    "must start with references/, templates/, scripts/, or assets/."
                ),
            },
            "file_content": {
                "type": "string",
                "description": "Support-file body for write_file.",
            },
        },
        "required": ["action"],
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
        """Construct the skill-manage tool.

        refactor-406-M3fix #4: prefer per-session resolution. When constructed with
        ``workspace_config_dirname`` (the 2-layer build_kernel path), the writer +
        registry are derived **per run** from ``ctx.session_metadata`` (workspace_root
        + workspace_config_dirname) plus the deployment ``extra_roots`` — so each agent
        writes/lists its own workspace skills (no shared repo_root registry) and
        skill_manage list aligns with ``list_skills`` / IM (one resolver).

        The fixed ``skill_root`` + ``registry`` path is kept for tests and the legacy
        product_profile path (bypasses per-session metadata lookup).
        """
        self._workspace_config_dirname = workspace_config_dirname
        self._extra_roots = tuple(extra_roots)
        self._pa_skill_root = pa_skill_root
        self._fixed_skill_root = skill_root.expanduser().resolve() if skill_root else None
        if skill_root is not None and registry is not None:
            self._fixed_writer: SkillWriter | None = SkillWriter(
                skill_root=skill_root, registry=registry
            )
            self._fixed_registry: SkillRegistry | None = registry
        else:
            self._fixed_writer = None
            self._fixed_registry = None
        # refactor-406-M3fix-r2 R2-3：fail fast at construction if neither a fixed
        # (skill_root + registry) nor a per-session (workspace_config_dirname) path is
        # configured — otherwise the misconfiguration only surfaces at first run().
        if self._fixed_writer is None and not self._workspace_config_dirname:
            raise ValueError(
                "SkillManageTool requires either (skill_root + registry) or "
                "workspace_config_dirname for per-session resolution"
            )

    def run(self, args: Mapping[str, Any], ctx: Any) -> Mapping[str, Any]:
        """Dispatch the requested action; return structured success/error dict."""
        action = str(args.get("action", ""))

        if action not in _SUPPORTED_ACTIONS:
            return {
                "success": False,
                "error": f"Unknown action '{action}'; supported: {sorted(_SUPPORTED_ACTIONS)}",
            }

        try:
            roots = self._resolve_skill_roots(ctx)
            metadata = getattr(ctx, "session_metadata", {}) or {}
            return self._dispatch(action, args, roots=roots, metadata=metadata)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Unexpected error: {exc}"}

    def _resolve_skill_roots(self, ctx: Any) -> ResolvedSkillRoots:
        """Resolve per-session skill roots from ctx, or the fixed test pair.

        Production (2-layer) path: derive ``<workspace_root>/<workspace_config_dirname>/
        skills`` from session_metadata as the write root, and a SkillRegistry searching
        that root FIRST then ``extra_roots`` (deployment global/compat) — mirroring
        ``Kernel.list_skills`` so writes land where list/IM read. Test/legacy path:
        return the fixed writer+registry bound at construction.
        """
        if (
            self._fixed_writer is not None
            and self._fixed_registry is not None
            and self._fixed_skill_root is not None
        ):
            return ResolvedSkillRoots(
                agent_skill_root=self._fixed_skill_root,
                search_roots=(self._fixed_skill_root,),
                registry=self._fixed_registry,
                agent_writer=self._fixed_writer,
                pa_skill_root=self._pa_skill_root.expanduser().resolve()
                if self._pa_skill_root is not None
                else None,
            )

        return resolve_skill_roots(
            ctx,
            workspace_config_dirname=self._workspace_config_dirname,
            extra_roots=self._extra_roots,
            pa_skill_root=self._pa_skill_root,
        )

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

    def _dispatch(
        self,
        action: str,
        args: Mapping[str, Any],
        *,
        roots: ResolvedSkillRoots,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if action == "create":
            return self._create(args, roots, metadata=metadata)
        if action == "edit":
            return self._edit(args, roots.agent_writer)
        if action == "patch":
            return self._patch(args, roots.agent_writer)
        if action == "list":
            return self._list(roots.registry)
        if action == "write_file":
            return self._write_file(args, roots.agent_writer)
        if action == "remove_file":
            return self._remove_file(args, roots.agent_writer)
        raise ValueError(f"Unhandled action '{action}'")  # unreachable

    def _write_file(
        self, args: Mapping[str, Any], writer: SkillWriter
    ) -> Mapping[str, Any]:
        name = args.get("name")
        file_path = args.get("file_path")
        file_content = args.get("file_content")
        if not name:
            return {"success": False, "error": "write_file action requires 'name'"}
        if not file_path:
            return {"success": False, "error": "write_file action requires 'file_path'"}
        if file_content is None:
            return {
                "success": False,
                "error": "write_file action requires 'file_content'",
            }
        path = writer.write_file(str(name), str(file_path), str(file_content))
        return {
            "success": True,
            "message": f"wrote support file '{file_path}' to skill '{name}' at {path}",
        }

    def _remove_file(
        self, args: Mapping[str, Any], writer: SkillWriter
    ) -> Mapping[str, Any]:
        name = args.get("name")
        file_path = args.get("file_path")
        if not name:
            return {"success": False, "error": "remove_file action requires 'name'"}
        if not file_path:
            return {
                "success": False,
                "error": "remove_file action requires 'file_path'",
            }
        path = writer.remove_file(str(name), str(file_path))
        return {
            "success": True,
            "message": f"removed support file '{file_path}' from skill '{name}'",
            "path": str(path),
        }

    def _create(
        self,
        args: Mapping[str, Any],
        roots: ResolvedSkillRoots,
        *,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        name = args.get("name")
        content = args.get("content")
        if not name:
            return {"success": False, "error": "create action requires 'name'"}
        if not content:
            return {"success": False, "error": "create action requires 'content'"}
        scope = str(args.get("scope") or "agent")
        writer = roots.writer_for_scope(scope)
        path = writer.create(str(name), str(content))
        ensure_skill_record(
            skill_root=Path(path).parent.parent,
            skill_name=str(name),
            source=source_from_metadata(dict(metadata)),
        )
        return {"success": True, "message": f"created skill '{name}' at {path}"}

    def _edit(self, args: Mapping[str, Any], writer: SkillWriter) -> Mapping[str, Any]:
        name = args.get("name")
        content = args.get("content")
        if not name:
            return {"success": False, "error": "edit action requires 'name'"}
        if not content:
            return {"success": False, "error": "edit action requires 'content'"}
        path = writer.edit(str(name), str(content))
        return {"success": True, "message": f"updated skill '{name}' at {path}"}

    def _patch(self, args: Mapping[str, Any], writer: SkillWriter) -> Mapping[str, Any]:
        name = args.get("name")
        old_string = args.get("old_string")
        new_string = args.get("new_string")
        if not name:
            return {"success": False, "error": "patch action requires 'name'"}
        if old_string is None:
            return {"success": False, "error": "patch action requires 'old_string'"}
        if new_string is None:
            return {"success": False, "error": "patch action requires 'new_string'"}
        path = writer.patch(
            str(name), old_string=str(old_string), new_string=str(new_string)
        )
        return {"success": True, "message": f"patched skill '{name}' at {path}"}

    def _list(self, registry: SkillRegistry) -> Mapping[str, Any]:
        skills = registry.list_skills()
        skill_list = [{"name": s.name, "description": s.description} for s in skills]
        return {"success": True, "skills": skill_list, "count": len(skill_list)}
