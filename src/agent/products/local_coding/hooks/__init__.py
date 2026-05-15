"""Built-in hook defaults for the local_coding product."""

# auto_mode_gate replaces bash_risk_gate in feat-333 (unified allow/deny/ask classifier).
# self_improvement added in feat-349-M3: background self-evolution hook.
DEFAULT_HOOK_MODULES = ["auto_mode_gate", "default_status", "realtime_stream", "usage_metrics", "self_improvement"]

__all__ = ["DEFAULT_HOOK_MODULES"]
