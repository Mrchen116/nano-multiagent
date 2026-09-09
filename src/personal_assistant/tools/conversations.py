"""Discover accessible conversations and inspect history without Inbox writes."""

from personal_assistant.tools.inbox import InboxTool, QueryPresenter


class ConversationsTool(InboxTool):
    """Query real accessible history through the global main Session scope."""

    name = "conversations"
    description = "List accessible conversations or read their history. These queries never consume Inbox messages."
    presenter = QueryPresenter("Conversations")
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "read"]},
            "target": {"type": "string"},
            "query": {"type": "string"},
            "before_message_id": {"type": "string"},
            "cursor": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["action"],
        "additionalProperties": False,
    }


def get_tool() -> ConversationsTool:
    """Return the standalone tool for product discovery."""
    return ConversationsTool()
