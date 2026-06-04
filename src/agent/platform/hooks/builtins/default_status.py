"""Default built-in hook module for shutdown/timeout status logging."""


def setup(hooks):  # noqa: ANN001, ANN201
    """Register lightweight built-in observe hooks for runtime status events."""

    def on_session_shutdown(event, ctx):  # noqa: ANN001
        ctx.logger.info(
            "builtin session shutdown observed",
            session_id=event.get("session_id"),
        )

    def on_run_timeout(event, ctx):  # noqa: ANN001
        ctx.logger.warning(
            "builtin run timeout observed",
            session_id=event.get("session_id"),
            run_id=event.get("run_id"),
        )

    hooks.on("session_shutdown", on_session_shutdown, priority=100, timeout_ms=500)
    hooks.on("run_timeout", on_run_timeout, priority=100, timeout_ms=500)
