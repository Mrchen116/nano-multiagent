"""Structured REPL turn rendering helpers."""

from typing import TextIO

from coding_cli.render.repl_summary import print_turn_summary


def print_repl_turn_summary(
    *,
    out: TextIO,
    payload: dict[str, object],
    context_budget_client: object | None = None,
) -> None:
    """Render one turn result with compact answer-first summary."""
    from coding_cli.render.repl_summary import _extract_message_content

    text_streamed = bool(payload.get("_text_streamed"))
    if not text_streamed:
        answer = _extract_message_content(payload)
        print("Assistant:", file=out)
        if answer is not None:
            print(answer, file=out)
        else:
            print("(empty)", file=out)

    print_turn_summary(out=out, payload=payload, context_budget_client=context_budget_client)


def print_repl_turn_error(
    *,
    out: TextIO,
    error: Exception,
    layer: str,
    suggestion: str,
) -> None:
    """Render one failed turn with compact answer-first summary."""
    print("Assistant: (empty)", file=out)
    print(f"State: failed | layer={layer}", file=out)
    print(f"Error: {error}", file=out)
    print(f"Hint: suggestion={suggestion}", file=out)
    print("Usage: unavailable", file=out)
