"""Discover accessible conversations and inspect history without Inbox writes."""

from personal_assistant.tools.inbox import InboxTool, QueryPresenter, serialize_page
from personal_assistant.tools.inbox_result import model_page


class ConversationsTool(InboxTool):
    """Query real accessible history through the global main Session scope."""

    name = "conversations"
    description = "Find chats by chat or member name (list), get complete members and mention tags (info), or read history (read). History returns newest messages first; next_cursor continues the page, before_message_id reads older messages. These queries never consume Inbox messages."
    presenter = QueryPresenter("Conversations")

    def serialize_result(self, output, error=None):
        """Keep the existing history query representation."""
        return serialize_page(model_page(output), error) if error is None else error

    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["list", "info", "read"]},
            "target": {
                "type": "string",
                "description": "Conversation ID from list; required for info/read.",
            },
            "query": {
                "type": "string",
                "description": "Optional chat or member name filter for list.",
            },
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
