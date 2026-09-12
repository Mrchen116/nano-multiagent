"""Versioned Auto security-monitor policy and shared source instructions.

Only shipped assets are adapted to the current product paths. Configured rule
text and application source instructions are inserted unchanged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Sequence

from agent.platform.config.auto_mode import AutoModeConfig

POLICY_VERSION = "cc-2.1.267-nano-v1"
_ASSET_ROOT = Path(__file__).with_name("auto_mode_policy_assets") / POLICY_VERSION


def _asset(name: str) -> str:
    return (_ASSET_ROOT / name).read_text(encoding="utf-8")


_SYSTEM_TEMPLATE = _asset("security_monitor.txt")
_DEFAULT_RULES: dict[str, list[str]] = json.loads(_asset("defaults.json"))
XML_S1_SUFFIX = _asset("s1_suffix.txt")
XML_S2_SUFFIX = _asset("s2_suffix.txt")
SCHEDULED_SOURCE_INSTRUCTIONS = _asset("scheduled_source.txt")
SYSTEM_SOURCE_INSTRUCTIONS = _asset("system_source.txt")
SYSTEM_WITH_HUMAN_SOURCE_INSTRUCTIONS = _asset("system_with_human_source.txt")
AGENT_SOURCE_INSTRUCTIONS = _asset("agent_source.txt")
SUMMARY_SOURCE_INSTRUCTIONS = _asset("summary_source.txt")
UNCLASSIFIED_SOURCE_INSTRUCTIONS = _asset("unclassified_source.txt")


def build_system_prompt(
    config: AutoModeConfig,
    *,
    workspace_root: Path,
    product_config_dir: Path,
    context_instructions: Sequence[str] = (),
    workspace_config_dirname: str | None = None,
) -> str:
    """Assemble the pinned policy with effective rules and actual product paths.

    Args:
        config: Effective global/workspace Auto configuration.
        workspace_root: Current session workspace.
        product_config_dir: Actual deployment-global product configuration root.
        context_instructions: Enabled tools' fixed application source guidance.
        workspace_config_dirname: Workspace configuration directory name. When
            omitted, use the product global root's basename.

    Returns:
        Complete classifier system policy, shared by both classification stages.
    """
    workspace_root = Path(workspace_root).expanduser()
    product_config_dir = Path(product_config_dir).expanduser()
    workspace_config_dir = workspace_root / (
        workspace_config_dirname or product_config_dir.name
    )
    paths = {
        "<nano_workspace_root>": str(workspace_root),
        "<nano_global_config_dir>": str(product_config_dir),
        "<nano_workspace_config_dir>": str(workspace_config_dir),
    }

    def with_paths(text: str) -> str:
        return re.sub(
            r"<nano_(?:workspace_root|global_config_dir|workspace_config_dir)>",
            lambda match: paths[match[0]],
            text,
        )

    replacements = {}
    for key, rules in _DEFAULT_RULES.items():
        defaults = tuple(with_paths(rule) for rule in rules)
        effective = _expand_rules(getattr(config, key), defaults)
        replacements[f"<nano_{key}_rules>"] = "\n".join(
            f"- {rule}" for rule in effective
        )
    # A single substitution avoids interpreting placeholder-shaped user text.
    prompt = re.sub(
        r"<nano_(?:allow|soft_deny|hard_deny|environment)_rules>",
        lambda match: replacements[match[0]],
        with_paths(_SYSTEM_TEMPLATE),
    )
    if context_instructions:
        prompt += "\n\n## Application Source Context\n\n" + "\n\n".join(
            context_instructions
        )
    return prompt


def _expand_rules(
    configured: tuple[str, ...], defaults: tuple[str, ...]
) -> tuple[str, ...]:
    if not configured:
        return defaults
    expanded: list[str] = []
    defaults_used = False
    for rule in configured:
        if rule == "$defaults":
            if not defaults_used:
                expanded.extend(defaults)
                defaults_used = True
        else:
            expanded.append(rule)
    return tuple(expanded)
