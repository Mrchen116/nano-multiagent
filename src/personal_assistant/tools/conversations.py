"""Discover accessible conversations and inspect history without Inbox writes."""

from personal_assistant.tools.inbox import InboxTool, QueryPresenter, serialize_page
from personal_assistant.tools.inbox_result import model_page


class ConversationsTool(InboxTool):
    """Query real accessible history through the global main Session scope."""

    name = "conversations"
    description = (
        "Global mode only: find conversations, look up members, or read history newest first. "
        "These queries do not mark Inbox messages as read. "
        "If next_cursor is returned, use it to continue; partial marks an incomplete message."
    )
    presenter = QueryPresenter("Conversations")

    def serialize_result(self, output, error=None):
        """Keep the existing history query representation."""
        return serialize_page(model_page(output), error) if error is None else error

    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "info", "read"],
                "description": "list: find conversations; info: get all members with user_id, name, type and mention tag; read: read message history.",
            },
            "target": {
                "type": "string",
                "description": "For info/read only, required: conversation_id (c_...) returned by list or inbox.",
            },
            "query": {
                "type": "string",
                "description": "For list only: filter by conversation or member name. Omit to list recent conversations.",
            },
            "before_message_id": {
                "type": "string",
                "description": "For read only: a message id from this conversation; read older messages, excluding this one. Do not combine with cursor.",
            },
            "cursor": {
                "type": "string",
                "description": "For list/read: copy next_cursor from the previous result and keep the same action, target and query. Omit on the first page.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "description": "For list/read only: maximum conversations for list or message parts for read (default 20). A long message may span parts; a page may contain fewer items.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }


def get_tool() -> ConversationsTool:
    """Return the standalone tool for product discovery."""
    return ConversationsTool()
