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
from agent.platform.tools.presentation import (
    SKILL_MANAGE_PRESENTER as _SKILL_MANAGE_PRESENTER,
)

# Actions supported by this tool (design §4 interface)
_SUPPORTED_ACTIONS = frozenset(
    {"create", "edit", "patch", "view", "list", "write_file", "remove_file"}
)


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
    presenter = (
        _SKILL_MANAGE_PRESENTER  # 决策 12: presentation travels with the tool object
    )

    description = (
        "Manage persistent skill files that teach you how to do classes of tasks.\n\n"
        "ACTIONS:\n"
        "- create: Create a new skill (name + content with YAML frontmatter).\n"
        "- edit: Fully replace an existing skill's SKILL.md content.\n"
        "- patch: Apply a find-and-replace to an existing skill (old_string → new_string).\n"
        "- view: Read an existing skill's SKILL.md content + its support files by name.\n"
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
                    "view",
                    "list",
                    "write_file",
                    "remove_file",
                ],
                "description": "The action to perform.",
            },
            "name": {
                "type": "string",
                "description": "Skill name (required for create/edit/patch/view/write_file/remove_file).",
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
            writer, registry = self._resolve_writer_registry(ctx)
            return self._dispatch(action, args, writer=writer, registry=registry)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"Unexpected error: {exc}"}

    def _resolve_writer_registry(self, ctx: Any) -> tuple[SkillWriter, SkillRegistry]:
        """Resolve the per-session (writer, registry) from ctx, or the fixed pair.

        Production (2-layer) path: derive ``<workspace_root>/<workspace_config_dirname>/
        skills`` from session_metadata as the write root, and a SkillRegistry searching
        that root FIRST then ``extra_roots`` (deployment global/compat) — mirroring
        ``Kernel.list_skills`` so writes land where list/IM read. Test/legacy path:
        return the fixed writer+registry bound at construction.
        """
        if self._fixed_writer is not None and self._fixed_registry is not None:
            return self._fixed_writer, self._fixed_registry

        metadata = getattr(ctx, "session_metadata", {}) or {}
        workspace_root = metadata.get("workspace_root")
        dirname = (
            metadata.get("workspace_config_dirname") or self._workspace_config_dirname
        )
        if not workspace_root or not dirname:
            raise RuntimeError(
                "skill_manage cannot resolve a per-session skill root: missing "
                "workspace_root or workspace_config_dirname in session_metadata. "
                "Ensure build_kernel threads workspace_config_dirname into "
                "default_session_metadata and runtime injects workspace_root per turn."
            )

        ws = Path(str(workspace_root)).expanduser().resolve()
        write_root = ws / str(dirname) / "skills"
        # Search roots: per-session workspace skills FIRST, then deployment extra_roots
        # (global/compat), deduped — same precedence as Kernel.list_skills (决策4).
        search_roots: list[Path] = [write_root]
        for root in self._extra_roots:
            resolved = Path(root).expanduser().resolve()
            if resolved not in search_roots:
                search_roots.append(resolved)
        registry = SkillRegistry(search_roots=tuple(search_roots))
        writer = SkillWriter(skill_root=write_root, registry=registry)
        return writer, registry

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
        writer: SkillWriter,
        registry: SkillRegistry,
    ) -> Mapping[str, Any]:
        if action == "create":
            return self._create(args, writer)
        if action == "edit":
            return self._edit(args, writer)
        if action == "patch":
            return self._patch(args, writer)
        if action == "view":
            return self._view(args, writer, registry)
        if action == "list":
            return self._list(registry)
        if action == "write_file":
            return self._write_file(args, writer)
        if action == "remove_file":
            return self._remove_file(args, writer)
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
        writer.remove_file(str(name), str(file_path))
        return {
            "success": True,
            "message": f"removed support file '{file_path}' from skill '{name}'",
        }

    def _create(
        self, args: Mapping[str, Any], writer: SkillWriter
    ) -> Mapping[str, Any]:
        name = args.get("name")
        content = args.get("content")
        if not name:
            return {"success": False, "error": "create action requires 'name'"}
        if not content:
            return {"success": False, "error": "create action requires 'content'"}
        path = writer.create(str(name), str(content))
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

    def _view(
        self, args: Mapping[str, Any], writer: SkillWriter, registry: SkillRegistry
    ) -> Mapping[str, Any]:
        name = args.get("name")
        if not name:
            return {"success": False, "error": "view action requires 'name'"}
        # Find the skill in the registry
        skills = registry.list_skills()
        skill = next((s for s in skills if s.name == str(name)), None)
        if skill is None:
            return {"success": False, "error": f"Skill '{name}' not found"}
        content = skill.location.read_text(encoding="utf-8")
        # Surface the skill's support files so the agent can see what's bundled
        # (and patch/extend it) without a generic filesystem read tool.
        try:
            support_files = writer.list_support_files(str(name))
        except ValueError:
            support_files = []
        return {
            "success": True,
            "name": str(name),
            "content": content,
            "location": str(skill.location),
            "support_files": support_files,
        }

    def _list(self, registry: SkillRegistry) -> Mapping[str, Any]:
        skills = registry.list_skills()
        skill_list = [{"name": s.name, "description": s.description} for s in skills]
        return {"success": True, "skills": skill_list, "count": len(skill_list)}
