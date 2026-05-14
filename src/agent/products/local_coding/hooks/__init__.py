"""Built-in hook defaults for the local_coding product."""

# self_improvement added in feat-349-M3: background self-evolution hook.
DEFAULT_HOOK_MODULES = ["bash_risk_gate", "default_status", "realtime_stream", "usage_metrics", "self_improvement"]

__all__ = ["DEFAULT_HOOK_MODULES"]
