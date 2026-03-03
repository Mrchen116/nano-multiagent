"""Map exceptions to user-facing suggestion/layer semantics for CLI output."""

_ERROR_LAYERS = {"input", "network", "runtime"}


def suggestion_for_exception(exc: Exception, *, default: str, mode: str | None = None) -> str:
    """Return actionable remediation suggestion for a CLI-visible exception."""
    explicit_suggestion = getattr(exc, "suggestion", None)
    if isinstance(explicit_suggestion, str) and explicit_suggestion.strip():
        return explicit_suggestion
    text = str(exc).lower()
    if "port" in text and "in use" in text:
        return "free the port, choose another local --base-url, or switch to --mode remote."
    if "remote mode requires --base-url" in text:
        return "pass --base-url <url> (or set NANO_MULTIAGENT_API_BASE_URL)."
    if "managed mode requires" in text:
        return "use a local http:// base URL for managed mode, or switch to --mode remote."
    if "managed startup llm options require --mode managed" in text:
        return "use --mode managed when passing --llm-provider/--llm-model/--llm-base-url/--llm-api-key/--llm-timeout-seconds."
    if "llm-config set requires at least one field" in text:
        return "try: llm-config set --provider anthropic (or provide another field)."
    if "--api-key and --clear-api-key cannot be used together" in text:
        return "choose either --api-key <value> or --clear-api-key."
    if "--timeout-seconds must be > 0" in text:
        return "set --timeout-seconds to a positive value, for example --timeout-seconds 30."
    if "--llm-timeout-seconds must be > 0" in text:
        return "set --llm-timeout-seconds to a positive value, for example --llm-timeout-seconds 30."
    if "timed out" in text or "timeout" in text:
        if mode == "remote":
            return "request timed out; check remote API latency or increase NANO_MULTIAGENT_API_TIMEOUT_SECONDS."
        if mode == "managed":
            return "request timed out; local API/LLM may be slow, retry or increase NANO_MULTIAGENT_API_TIMEOUT_SECONDS."
        return "request timed out; retry or increase NANO_MULTIAGENT_API_TIMEOUT_SECONDS."
    if "connection refused" in text or "connecterror" in text or "nodename nor servname" in text:
        if mode == "remote":
            return "check --base-url and ensure the remote API server is reachable."
        if mode == "managed":
            return "managed mode could not reach the local API; check startup logs/port, then retry or switch to --mode remote."
        return "check --base-url and ensure API server is running."
    if "missing api token" in text or "unauthorized" in text or "401" in text:
        return "check --token or NANO_MULTIAGENT_API_TOKEN and retry."
    return default


def error_layer_for_exception(exc: Exception, *, default: str = "runtime") -> str:
    """Classify exception into input/network/runtime layer for user guidance."""
    explicit_layer = getattr(exc, "layer", None)
    if isinstance(explicit_layer, str):
        normalized_layer = explicit_layer.strip().lower()
        if normalized_layer in _ERROR_LAYERS:
            return normalized_layer

    text = str(exc).lower()
    if (
        "run failed" in text
        or "run_id=" in text
        or "run_execution_failed" in text
        or "stop_reason" in text
        or "root_cause=" in text
    ):
        return "runtime"
    if isinstance(exc, ValueError):
        return "input"
    if (
        "request failed (" in text
        or "timed out" in text
        or "timeout" in text
        or "connection refused" in text
        or "connecterror" in text
        or "nodename nor servname" in text
        or "name or service not known" in text
        or "unauthorized" in text
        or "missing api token" in text
    ):
        return "network"
    if default in _ERROR_LAYERS:
        return default
    return "runtime"
