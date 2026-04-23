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
    ordered_updates: list[dict[str, str]] = []
    view = payload.get("_repl_view")
    if isinstance(view, dict):
        raw_updates = view.get("ordered_updates")
        if isinstance(raw_updates, list):
            for item in raw_updates:
                if not isinstance(item, dict):
                    continue
                kind = item.get("kind")
                text = item.get("text")
                if isinstance(kind, str) and kind in {"assistant", "tool"} and isinstance(text, str) and text:
                    ordered_updates.append({"kind": kind, "text": text})

    if not text_streamed:
        if ordered_updates:
            for item in ordered_updates:
                if item["kind"] == "assistant":
                    print("Assistant:", file=out)
                    print(item["text"], file=out)
                else:
                    print(item["text"], file=out)
        else:
            answer = _extract_message_content(payload)
            print("Assistant:", file=out)
            if answer is not None:
                print(answer, file=out)
            else:
                print("(empty)", file=out)

    summary_payload = dict(payload) if ordered_updates else payload
    if ordered_updates:
        summary_payload["_ordered_rendered"] = True
    print_turn_summary(out=out, payload=summary_payload, context_budget_client=context_budget_client)


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
