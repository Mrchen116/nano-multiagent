"""Shared automatic approval policy and existing interactive/unattended routing.

Tool-specific decisions precede automatic classification. The pinned CC policy,
S1/S2 request and source-aware transcript are assembled by private helper modules.
The intercept owns its timeout because an interactive permission request may park.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
import time
from pathlib import Path
from typing import Any, Mapping

_log = logging.getLogger("agent.platform.hooks.auto_mode_gate")

from agent.core.runs.origin import RunOrigin
from agent.platform.hooks.builtins._auto_mode_transcript import (
    build_transcript_entries,
    serialize_transcript,
)
from agent.platform.config.auto_mode import AutoModeConfig, load_auto_mode_config
from agent.platform.hooks.tool_approval_model import get_tool_approval_model
from agent.platform.permissions.broker import (
    PermissionBroker,
    PermissionDecision,
    PermissionRequest,
    PermissionResponse,
    _default_options_for_tool,
)
# ToolSafety / load_tool_safety_config removed in M6 (D7): bash policy now
# lives in bash_policy.py and is dispatched via BashTool.check_permissions.

from agent.platform.hooks.builtins._auto_mode_policy import (
    POLICY_VERSION,
    XML_S1_SUFFIX,
    XML_S2_SUFFIX,
    build_system_prompt,
)

# ---------------------------------------------------------------------------
# Safe-tool allowlist
# ---------------------------------------------------------------------------

SAFE_TOOL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "read",
        "web_search",
        "skill_view",
        "task_stop",
        "agent",
        "memory",
    }
)

# Unattended run origins (no human present to answer ask prompts).
# feat-394-M7 R5-1 fix: cron runs are isolated and unattended; tool ask has no human
# to answer, so they must walk the unattended fallback path (auto-deny or auto-allow).
_UNATTENDED_ORIGINS: frozenset[str] = frozenset(
    {
        RunOrigin.HEARTBEAT.value,
        "heartbeat",  # string form
        RunOrigin.BACKGROUND_TASK.value,
        RunOrigin.CRON.value,
        "cron",  # string form
    }
)


# ---------------------------------------------------------------------------
# Public API used by tests
# ---------------------------------------------------------------------------


def is_safe_tool(tool_name: str, config: AutoModeConfig) -> bool:
    """Return True if tool should bypass the classifier entirely.

    Checks built-in SAFE_TOOL_ALLOWLIST and user-configured always_allow_tools.

    Args:
        tool_name: Name of the tool being called.
        config: AutoModeConfig with user-configured extensions.

    Returns:
        True if the tool is safe and should be auto-allowed.
    """
    if config.enabled and tool_name == "bash":
        return False
    return tool_name in SAFE_TOOL_ALLOWLIST or tool_name in config.always_allow_tools


def build_yolo_system_prompt(config: AutoModeConfig) -> str:
    """Assemble policy for callers without a resolved product execution scope."""
    return build_system_prompt(
        config, workspace_root=Path.cwd(), product_config_dir=Path.home() / ".nano"
    )


def strip_thinking(text: str) -> str:
    """Remove <thinking>...</thinking> blocks. Pixel-perfect CC stripThinking.

    Prevents CoT content from interfering with <block>/<reason> parsing.

    Args:
        text: Raw classifier response text.

    Returns:
        Text with thinking blocks removed.
    """
    text = re.sub(r"<thinking>[\s\S]*?</thinking>", "", text)
    text = re.sub(r"<thinking>[\s\S]*$", "", text)
    return text


def parse_xml_block(text: str) -> bool | None:
    """Parse <block>yes/no</block>. Pixel-perfect CC parseXmlBlock.

    Args:
        text: Classifier response text (may have thinking blocks).

    Returns:
        True = block, False = allow, None = parse failure.
    """
    cleaned = strip_thinking(text)
    matches = re.findall(r"<block>(yes|no)\b(</block>)?", cleaned, re.IGNORECASE)
    if not matches:
        return None
    return matches[0][0].lower() == "yes"


def parse_xml_reason(text: str) -> str | None:
    """Parse <reason>...</reason>. Pixel-perfect CC parseXmlReason.

    Args:
        text: Classifier response text.

    Returns:
        Reason string, or None if absent.
    """
    cleaned = strip_thinking(text)
    match = re.search(r"<reason>([\s\S]*?)</reason>", cleaned)
    return match.group(1).strip() if match else None


# ---------------------------------------------------------------------------
# Two-stage classifier
# ---------------------------------------------------------------------------


async def _classify_action(
    ctx: Any, system_prompt: str, user_prompt: str, *, model: str | None = None
) -> PermissionDecision:
    """Run the pinned S1/S2 request shape and distinguish faults from valid denials."""
    for stage, suffix, budget, timeout in (
        (1, XML_S1_SUFFIX, 2112, 30.0),
        (2, XML_S2_SUFFIX, 10240, 60.0),
    ):
        started = time.monotonic()
        source = "classifier_unavailable"
        usage = None
        try:
            kwargs = dict(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt + suffix,
                max_tokens=budget,
                temperature=0,
                extra_body={"thinking": {"type": "disabled"}},
            )
            if stage == 1:
                kwargs["stop_sequences"] = ["</block>"]
            result = await asyncio.wait_for(ctx.call_model(**kwargs), timeout=timeout)
            usage = getattr(result, "raw", {}).get("usage")
            blocked = parse_xml_block(result.content)
            if blocked is None:
                source = "parsing_error"
                decision = PermissionDecision(
                    behavior="ask",
                    reason=f"Classifier stage {stage} returned no valid verdict",
                    rule_source=source,
                )
            elif blocked and stage == 1:
                source = "stage_one_block"
                continue
            else:
                source = "classifier_block" if blocked else "classifier_allow"
                decision = PermissionDecision(
                    behavior="deny" if blocked else "allow",
                    reason=(parse_xml_reason(result.content) or "Blocked by classifier")
                    if blocked
                    else "Allowed by classifier",
                    rule_source=source,
                )
        except Exception as exc:
            error_text = str(exc).lower()
            if any(
                marker in error_text
                for marker in (
                    "prompt too long",
                    "prompt_too_long",
                    "context_length_exceeded",
                    "maximum context length",
                    "context window",
                    "too many tokens",
                )
            ):
                source = "prompt_too_long"
            decision = PermissionDecision(
                behavior="ask",
                reason=f"Classifier stage {stage} unavailable ({type(exc).__name__}: {exc})",
                rule_source=source,
            )
        finally:
            _log.info(
                "auto_classifier_stage",
                extra={
                    "policy_version": POLICY_VERSION,
                    "stage": stage,
                    "model": model,
                    "prompt_chars": len(system_prompt) + len(user_prompt) + len(suffix),
                    "prompt_bytes": len(
                        (system_prompt + user_prompt + suffix).encode("utf-8")
                    ),
                    "elapsed_ms": round((time.monotonic() - started) * 1000),
                    "decision_source": source,
                    "usage": usage,
                },
            )
        return decision
    raise AssertionError("the second classifier stage must return a decision")


# ---------------------------------------------------------------------------
# Gate hook
# ---------------------------------------------------------------------------


def _tool_registry_from_ctx(ctx: Any) -> Any | None:
    """Return the registry injected into HookContext metadata, if present."""

    metadata = getattr(ctx, "metadata", {}) or {}
    if not isinstance(metadata, Mapping):
        return None
    return metadata.get("tool_registry")


def _tool_instance_from_registry(ctx: Any, tool_name: str) -> Any | None:
    """Resolve a tool instance by name from the hook context registry."""

    tool_registry = _tool_registry_from_ctx(ctx)
    get_tool = getattr(tool_registry, "get", None)
    if not callable(get_tool):
        return None
    return get_tool(tool_name)


def _project_tool_for_classifier(
    tool_instance: Any,
    tool_name: str,
    tool_input: Mapping[str, Any],
) -> str | None:
    """Return the classifier-visible projection supplied by a tool instance.

    ``None`` means the tool does not implement the projection contract. A returned
    empty string is an explicit no-action projection and is fail-closed for the
    current action before classifier dispatch.
    """

    project = getattr(tool_instance, "to_auto_classifier_input", None)
    if not callable(project):
        return None
    projection = project(dict(tool_input))
    if projection is None:
        return ""
    return str(projection)


def _project_historical_tool_use_for_classifier(tool_name: str, tool_input: Any) -> str:
    """Project recorded history without consulting today's live tool registry."""

    if isinstance(tool_input, Mapping):
        stable_input: Any = dict(tool_input)
    else:
        stable_input = tool_input
    return json.dumps(
        {"tool": tool_name, "input": stable_input},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _build_transcript_user_message(
    ctx: Any, tool_name: str, current_projection: str
) -> str:
    """Build one immutable transcript, ending with the current proposed action."""
    history = getattr(ctx, "message_history", None) or []
    metadata = getattr(ctx, "metadata", {}) or {}

    def project_result(name: str, content: Any) -> str | None:
        tool = _tool_instance_from_registry(ctx, name)
        project = getattr(tool, "to_auto_classifier_result", None)
        return project(content) if callable(project) else None

    inherited = metadata.get("parent_approval_context") or []
    entries = list(inherited) + build_transcript_entries(
        list(history),
        project_tool_result=project_result,
        prior_assistant_context=metadata.get("kind") != "subagent",
    )
    # The current action has neither an outcome nor host context.
    entries.append(
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "name": tool_name, "input": current_projection}
            ],
        }
    )
    serialized = serialize_transcript(
        entries, live_context=metadata.get("_live_tool_context")
    )
    return f"<transcript>\n{serialized}\n</transcript>"


async def _handle_ask(
    ctx: Any,
    tool_name: str,
    tool_input: dict,
    reason: str,
    run_id: str | None,
    session_id: str,
    config: AutoModeConfig,
    broker: PermissionBroker | None,
) -> dict:
    """Park hook coroutine waiting for user decision via request_permission.

    If ctx.request_permission is available, uses it. Otherwise falls back
    to deny (fail-closed when no permission channel is wired).

    Args:
        ctx: HookContext with optional request_permission capability.
        tool_name: Tool being evaluated.
        tool_input: Tool arguments.
        reason: Human-readable reason for the ask.
        run_id: Current run id for broker deny-count reset.
        session_id: Session id for allowlist tracking.
        config: AutoModeConfig.
        broker: PermissionBroker or None.

    Returns:
        Hook intercept result dict: {"block": bool, ...}
    """
    request_permission = getattr(ctx, "request_permission", None)
    if request_permission is None:
        # No permission channel wired — fail-closed
        return {"block": True, "reason": "no permission channel (fail-closed)"}

    request_id = str(uuid.uuid4())
    options = _default_options_for_tool(tool_name)
    req = PermissionRequest(
        id=request_id,
        tool_name=tool_name,
        tool_input=tool_input,
        question=f"Allow {tool_name}? {reason}",
        options=options,
    )

    try:
        response: PermissionResponse = await request_permission(req)
    except Exception as exc:
        return {"block": True, "reason": f"permission request failed: {exc}"}

    decision = response.decision
    tool_instance = _tool_instance_from_registry(ctx, tool_name)
    identity_fn = getattr(tool_instance, "permission_identity", None)
    decision_fn = getattr(tool_instance, "on_permission_decision", None)
    if callable(identity_fn) and callable(decision_fn):
        try:
            identity = identity_fn(tool_input, ctx)
            decision_fn(identity, decision, auto_mode=config.enabled)
        except (
            Exception
        ) as exc:  # tool-owned persistence must not break broker resolution
            _log.error(
                "tool permission decision callback failed",
                extra={"tool_name": tool_name, "error": str(exc)},
            )

    # feat-434-M1: a USER decision (allow_*/deny) carries an ``approval`` signal so
    # downstream can render the gate verdict 已授权 / 已拒绝. This ONLY fires on the
    # ask path (this function); auto-allow / auto-block return earlier without it, so
    # approval stays None for non-user-decided calls (gate region not shown).
    if decision == "allow_once":
        if broker:
            broker.record_auto_decision(session_id, True)
        return {"block": False, "approval": "user_allow"}

    if decision == "allow_session":
        if broker:
            broker.add_session_allowlist(session_id, tool_name)
            broker.record_auto_decision(session_id, True)
        return {"block": False, "approval": "user_allow"}

    if decision == "allow_always":
        # Write-back to workspace config is a M2+ concern for PA product layer.
        # Here we just grant and reset.
        if broker:
            broker.record_auto_decision(session_id, True)
        return {"block": False, "approval": "user_allow"}

    # deny
    # feat-440-M2 (F1): keep the reason empty when the user gave none — do NOT
    # forge a "user denied" placeholder. A non-empty reason here makes build_reject_message
    # 选择表 Row 3 (bare user_deny → concise REJECT_MESSAGE) unreachable and feeds the
    # LLM "...the user said:\nuser denied" instead. ``or ""`` keeps it a str so the
    # downstream ``isinstance(br, str) and br`` guard treats it as "no reason"
    # (empty str and None behave the same there).
    return {
        "block": True,
        "reason": response.reason or "",
        "approval": "user_deny",
    }


def _interaction(metadata: Mapping[str, Any]) -> str:
    global_interaction = metadata.get("auto_mode_interaction") == "return_to_agent"
    if global_interaction and metadata.get("kind") == "subagent":
        return "return_to_agent"
    origin = str(metadata.get("run_origin", "user"))
    if origin in {RunOrigin.HEARTBEAT.value, RunOrigin.CRON.value}:
        return "unattended"
    if global_interaction:
        return "return_to_agent"
    if origin in _UNATTENDED_ORIGINS or metadata.get("workflow_unattended") is True:
        return "unattended"
    return "interactive"


def _verdict(
    block: bool, reason: str, source: str, *, category: str | None = None
) -> dict[str, Any]:
    return {
        "block": block,
        "reason": reason,
        "decision_source": source,
        "category": category or source,
        "policy_version": POLICY_VERSION,
    }


def setup(hooks: Any) -> None:
    """Install the single permission intercept; its own waits define the timeout."""

    async def on_tool_call(event: Mapping[str, Any], ctx: Any) -> dict | None:
        tool_name = str(event.get("name", "")).strip()
        tool_input = (
            dict(event["args"]) if isinstance(event.get("args"), Mapping) else {}
        )
        session_id = getattr(ctx, "session_id", "")
        metadata = getattr(ctx, "metadata", {}) or {}
        run_id = metadata.get("run_id")
        broker = metadata.get("permission_broker")
        route = _interaction(metadata)
        loader = metadata.get("_auto_mode_config_loader")
        if callable(loader):
            config = loader()
        else:
            root = metadata.get("workspace_config_root")
            repo = getattr(ctx, "repo_root", None)
            config = load_auto_mode_config(
                global_config_dir=None,
                workspace_config_dir=Path(root)
                if root
                else repo / ".nano"
                if repo
                else None,
            )
        inherited = metadata.get("inherited_auto_mode_config")
        if isinstance(inherited, dict):
            from agent.platform.config.auto_mode import _parse_auto_mode_config

            config = _parse_auto_mode_config(inherited)

        def allow() -> None:
            if broker:
                broker.record_auto_decision(session_id, True)
            return None

        async def escalate(
            reason: str, source: str, *, safety_locked: bool = False
        ) -> dict:
            if route == "return_to_agent":
                return _verdict(True, reason, source)
            if route == "unattended":
                if safety_locked:
                    return _verdict(True, reason, "manual_required")
                permitted = config.unattended_fallback == "allow"
                if permitted:
                    allow()
                return _verdict(
                    not permitted,
                    f"{reason}; unattended fallback: {config.unattended_fallback}",
                    "unattended_fallback",
                    category=source,
                )
            result = await _handle_ask(
                ctx, tool_name, tool_input, reason, run_id, session_id, config, broker
            )
            return {**_verdict(bool(result.get("block")), reason, source), **result}

        tool = _tool_instance_from_registry(ctx, tool_name)
        check = getattr(tool, "check_permissions", None)
        checked = None
        if callable(check):
            try:
                checked = check(tool_input, ctx)
            except Exception as exc:
                _log.error(
                    "tool_permission_check_failed",
                    extra={"tool_name": tool_name, "error": str(exc)},
                )
                checked = PermissionDecision(
                    behavior="ask",
                    reason=f"Permission check failed for {tool_name}: {exc}",
                    decision_reason={"type": "safety_check"},
                )
        behavior = getattr(checked, "behavior", "passthrough")
        reason = (
            getattr(checked, "reason", "") or f"permission required for {tool_name}"
        )
        safety_locked = (
            behavior == "ask"
            and isinstance(checked.decision_reason, dict)
            and checked.decision_reason.get("type") == "safety_check"
        )
        if safety_locked:
            return await escalate(reason, "manual_required", safety_locked=True)
        # Skip remains the user's existing explicit mode; Auto wide grants cannot mask deny.
        if config.dangerously_skip_permissions:
            return allow()
        if config.enabled and behavior == "deny":
            return _verdict(True, reason, "explicit_deny")
        if (
            broker
            and broker.is_session_allowed(session_id, tool_name)
            and not (config.enabled and tool_name == "bash")
        ):
            return allow()
        if is_safe_tool(tool_name, config):
            return allow()
        if behavior == "allow":
            return allow()
        if behavior == "deny":
            return _verdict(True, reason, "explicit_deny")
        if behavior == "ask":
            if tool_name == "Workflow" and (
                metadata.get("workflow_ultracode") is True
                or metadata.get("run_origin") != RunOrigin.HUMAN.value
            ):
                return allow()
            return await escalate(reason, "manual_required")

        try:
            projection = (
                _project_tool_for_classifier(tool, tool_name, tool_input)
                if tool is not None
                else None
            )
            if projection is None:
                raise ValueError(f"missing classifier projection for {tool_name}")
            if not projection.strip():
                raise ValueError(f"empty classifier projection for {tool_name}")
            transcript = _build_transcript_user_message(ctx, tool_name, projection)
        except Exception as exc:
            return _verdict(
                True,
                f"classifier projection failed for {tool_name}: {exc}",
                "projection_error",
            )

        registry = _tool_registry_from_ctx(ctx)
        specs = (
            registry.list_specs()
            if registry is not None and callable(getattr(registry, "list_specs", None))
            else ()
        )
        context_instructions = []
        for spec in specs:
            instructions = getattr(
                registry.get(spec.name), "auto_classifier_context_instructions", None
            )
            if (
                isinstance(instructions, str)
                and instructions
                and instructions not in context_instructions
            ):
                context_instructions.append(instructions)
        repo_root = getattr(ctx, "repo_root", None) or Path.cwd()
        global_root = metadata.get("global_config_root") or Path.home() / metadata.get(
            "workspace_config_dirname", ".nano"
        )
        system_prompt = build_system_prompt(
            config,
            workspace_root=repo_root,
            product_config_dir=Path(global_root),
            workspace_config_dirname=metadata.get("workspace_config_dirname"),
            context_instructions=context_instructions,
        )
        decision = await _classify_action(
            ctx,
            system_prompt,
            transcript,
            model=metadata.get(
                "inherited_tool_approval_model", get_tool_approval_model(hooks)
            ),
        )
        if decision.behavior == "allow":
            return allow()
        if decision.behavior == "deny":
            if broker:
                consecutive, total = broker.record_auto_decision(
                    session_id, False, total_deny_limit=config.total_deny_limit
                )
                if consecutive >= config.deny_limit or total >= config.total_deny_limit:
                    return await escalate(decision.reason, "classifier_block")
            return _verdict(True, decision.reason, "classifier_block")
        return await escalate(decision.reason, decision.rule_source)

    hooks.on("tool_call", on_tool_call, priority=20, timeout_ms=None, mode="intercept")
