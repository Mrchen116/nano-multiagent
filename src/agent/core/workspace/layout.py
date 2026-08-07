"""Pure workspace layout and execution-scope contracts.

The core owns path derivation but deliberately does not discover extensions or
read product configuration.  SDK composition supplies those capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    """Derive every kernel-managed path for one workspace configuration directory."""

    workspace_root: Path
    config_dirname: str = ".nano"

    def __post_init__(self) -> None:
        root = self.workspace_root.expanduser().resolve()
        dirname = self.config_dirname.strip()
        if (
            dirname in {".", ".."}
            or not dirname.startswith(".")
            or "/" in dirname
            or "\\" in dirname
        ):
            raise ValueError("workspace config directory must be a dot-prefixed name")
        object.__setattr__(self, "workspace_root", root)
        object.__setattr__(self, "config_dirname", dirname)

    @property
    def config_root(self) -> Path:
        """Return the product-selected configuration root in this workspace."""

        return self.workspace_root / self.config_dirname

    @property
    def sessions(self) -> Path:
        """Return the durable session transcript directory."""

        return self.config_root / "sessions"

    @property
    def memory(self) -> Path:
        """Return the workspace memory directory."""

        return self.config_root / "memory"

    @property
    def skills(self) -> Path:
        """Return the workspace skill directory."""

        return self.config_root / "skills"

    @property
    def tools(self) -> Path:
        """Return the workspace tool-extension directory."""

        return self.config_root / "tools"

    @property
    def hooks(self) -> Path:
        """Return the workspace hook-extension directory."""

        return self.config_root / "hooks"

    @property
    def policy(self) -> Path:
        """Return the workspace bash-policy file."""

        return self.config_root / "policy.toml"

    @property
    def background_tasks(self) -> Path:
        """Return the workspace background-output directory."""

        return self.config_root / "background-tasks"

    @property
    def tool_results(self) -> Path:
        """Return the workspace oversized-tool-result directory."""

        return self.config_root / "tool-results"


@dataclass(frozen=True, slots=True)
class WorkspaceExecutionScope:
    """Immutable per-workspace capabilities selected for a single execution.

    Concrete registry, runner and policy types live in sibling layers.  Keeping
    them as ports here prevents core from importing platform implementation.
    """

    layout: WorkspaceLayout
    tool_registry: Any
    hook_runner: Any
    tool_result_compressor: Any
    bash_policy_overrides: Any
    auto_mode_config_loader: Callable[[], Any]

    def metadata(self, values: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        """Return immutable hook metadata bound to this exact workspace scope."""

        merged = dict(values or {})
        merged.update(
            {
                "workspace_root": str(self.layout.workspace_root),
                "workspace_config_dirname": self.layout.config_dirname,
                "workspace_config_root": str(self.layout.config_root),
                "tool_registry": self.tool_registry,
                "_auto_mode_config_loader": self.auto_mode_config_loader,
                "bash_policy_overrides": self.bash_policy_overrides,
                "_workspace_execution_scope": self,
            }
        )
        return MappingProxyType(merged)
