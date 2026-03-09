"""Built-in hook that gates unlisted bash commands via LLM risk review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from nano_multiagent.platform.tools.safety import ToolSafety, load_tool_safety_config


def setup(hooks):  # noqa: ANN001, ANN201
    """Register tool-call intercept hook for bash risk gating."""

    def on_tool_call(event: Mapping[str, Any], ctx):  # noqa: ANN001
        if str(event.get("name", "")).strip() != "bash":
            return None
        args = event.get("args")
        if not isinstance(args, Mapping):
            return None
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            return None

        repo_root = ctx.repo_root or Path.cwd()
        safety = ToolSafety(
            repo_root=repo_root,
            config=load_tool_safety_config(repo_root=repo_root),
        )
        decision = safety.check_command_policy(command, tool_name="bash")
        if decision.status == "denied":
            return {"block": True, "reason": _reason("denylist blocked", decision.details)}
        if decision.status == "allowed":
            return None

        try:
            review = ctx.call_model(
                system_prompt=(
                    "You are a shell safety gate. "
                    "Return strict JSON only with keys: risk, reason. "
                    "risk must be either \"safe\" or \"unsafe\"."
                ),
                user_prompt=(
                    "Assess this shell command for security risk.\n"
                    f"command: {command}"
                ),
            )
            risk, reason = _parse_risk_review(review.content)
        except Exception as exc:  # pragma: no cover - defensive fail-closed fallback.
            return {"block": True, "reason": f"risk review failed: {type(exc).__name__}: {exc}"}

        if risk == "safe":
            ctx.logger.info(
                "bash risk review passed",
                model=review.model,
                reason=reason,
            )
            return {"allow_unlisted": True}

        return {
            "block": True,
            "reason": _reason(
                reason or "risk review marked command as unsafe",
                {"model": review.model},
            ),
        }

    hooks.on("tool_call", on_tool_call, priority=20, timeout_ms=12000)


def _reason(message: str, details: Mapping[str, Any]) -> str:
    if not details:
        return message
    fields = ", ".join(f"{key}={value!r}" for key, value in sorted(details.items()))
    return f"{message} ({fields})"


def _parse_risk_review(content: str) -> tuple[str, str]:
    payload = _parse_json_object(content)
    risk = str(payload.get("risk", "unsafe")).strip().lower()
    reason = str(payload.get("reason", "")).strip()
    if not reason:
        reason = f"risk classifier returned: {risk or 'unknown'}"
    return risk, reason


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}
