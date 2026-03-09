"""Compatibility facade for CLI command orchestration module."""

from nano_multiagent.apps.coding_cli.commands import build_parser, run_cli
from nano_multiagent.apps.coding_cli.commands import _consume_async_run_events
from nano_multiagent.apps.coding_cli.commands import _context_budget_hint_for_ratio
from nano_multiagent.apps.coding_cli.commands import _context_budget_prefix
from nano_multiagent.apps.coding_cli.commands import _error_layer_for_exception
from nano_multiagent.apps.coding_cli.commands import _extract_context_budget_metrics
from nano_multiagent.apps.coding_cli.commands import _merge_text_delta
from nano_multiagent.apps.coding_cli.commands import _print_context_budget_snapshot
from nano_multiagent.apps.coding_cli.commands import _print_event_preview
from nano_multiagent.apps.coding_cli.commands import _send_message_with_async_events
from nano_multiagent.apps.coding_cli.commands import _suggestion_for_exception
from nano_multiagent.apps.coding_cli.commands import _supports_async_repl_events

__all__ = ["build_parser", "run_cli"]
