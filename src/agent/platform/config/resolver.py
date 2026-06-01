"""Config resolver: converts a ProductProfile into concrete filesystem paths.

All path resolution logic is centralized here. No other module should hard-code
product-specific directory names like ``.nanocode`` or ``.codex``.

Architecture constraints:
- ``session_db_path()`` is always in ``global_config_root()``; never in the
  workspace. This prevents session state from leaking into version control.
- ``compat_skill_roots`` have the lowest priority; they exist for backward
  compatibility with users who already have ``~/.codex/skills``.
- When no ``workspace_root`` is provided, workspace-relative roots are omitted
  (not defaulted to CWD) to avoid surprising behavior in server contexts.
"""

from __future__ import annotations

from pathlib import Path

from agent.products.base import ProductProfile


class ConfigResolver:
    """Resolve a ProductProfile into concrete filesystem paths.

    Args:
        profile: Product configuration holding path field declarations.
        workspace_root: Optional workspace root; when ``None``, workspace-relative
            roots (e.g. ``<workspace>/.nanocode/tools``) are omitted from results.
    """

    def __init__(
        self,
        *,
        profile: ProductProfile,
        workspace_root: Path | None = None,
    ) -> None:
        self._profile = profile
        self._workspace_root = (
            workspace_root.expanduser().resolve()
            if workspace_root is not None
            else None
        )

    def global_config_root(self) -> Path:
        """Return the absolute product-global config directory.

        Returns:
            Expanded and resolved ``profile.global_config_home``; always absolute.

        Raises:
            ValueError: When ``profile.global_config_home`` is ``None``.
        """

        home = self._profile.global_config_home
        if home is None:
            raise ValueError(
                f"ProductProfile '{self._profile.product_id}' has no global_config_home set"
            )
        return home.expanduser().resolve()

    def workspace_config_root(self) -> Path | None:
        """Return the absolute per-workspace config directory, or ``None``.

        Returns:
            ``<workspace_root>/<workspace_config_dirname>`` when both workspace
            root and dirname are configured; ``None`` otherwise.
        """

        if self._workspace_root is None:
            return None
        dirname = self._profile.workspace_config_dirname
        if not dirname:
            return None
        return self._workspace_root / dirname

    def session_db_path(self) -> Path:
        """Return the absolute path to the SQLite sessions database.

        The database always lives in ``global_config_root()`` so it is never
        accidentally committed to version control or duplicated per workspace.

        Returns:
            ``<global_config_root>/<session_db_filename>``; always absolute.
        """

        return self.global_config_root() / self._profile.session_db_filename

    def user_tool_roots(self) -> tuple[Path, ...]:
        """Return tool plugin search roots in precedence order (workspace first).

        Returns:
            Ordered tuple of directories to scan for user-provided tools.
            Workspace root (if configured) precedes the global root.
        """

        return self._build_roots("tools")

    def user_hook_roots(self) -> tuple[Path, ...]:
        """Return hook plugin search roots in precedence order (workspace first).

        Returns:
            Ordered tuple of directories to scan for user-provided hooks.
            Workspace root (if configured) precedes the global root.
        """

        return self._build_roots("hooks")

    def user_skill_roots(self) -> tuple[Path, ...]:
        """Return skill search roots in precedence order.

        Priority: workspace > global > compat roots.
        Duplicates are removed (compat roots equal to global are deduplicated).

        Returns:
            Ordered, deduplicated tuple of directories to scan for skills.
        """

        base = list(self._build_roots("skills"))
        # Append compat roots at lowest priority, deduplicating against existing.
        for raw_compat in self._profile.compat_skill_roots:
            resolved = raw_compat.expanduser().resolve()
            if resolved not in base:
                base.append(resolved)
        return tuple(base)

    def user_memory_root(self) -> Path | None:
        """Return the absolute per-workspace memory directory, or ``None``.

        Memory files (``MEMORY.md``, ``USER.md``) live under
        ``<workspace_root>/<workspace_config_dirname>/memory/``.
        Returns ``None`` when ``workspace_root`` or ``workspace_config_dirname``
        is not configured — callers should skip memory injection in that case.

        Returns:
            ``<workspace_config_root>/memory`` when both workspace root and
            dirname are configured; ``None`` otherwise.
        """

        ws_root = self.workspace_config_root()
        if ws_root is None:
            return None
        return ws_root / "memory"

    # --- Internal helpers ---

    def _build_roots(self, subdir: str) -> tuple[Path, ...]:
        """Return [workspace/<subdir>, global/<subdir>] omitting missing roots."""

        roots: list[Path] = []
        ws_root = self.workspace_config_root()
        if ws_root is not None:
            roots.append(ws_root / subdir)
        roots.append(self.global_config_root() / subdir)
        return tuple(roots)
