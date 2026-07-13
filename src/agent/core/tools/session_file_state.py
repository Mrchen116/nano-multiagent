"""Compatibility imports for conversation-owned file state.

Production ownership moved to :mod:`agent.core.session.context_state`; this module
remains only while tool imports are cut over in the same change unit.
"""

from agent.core.session.context_state import (
    FileReadState,
    SessionFileState,
    read_file_slice,
)

__all__ = ["FileReadState", "SessionFileState", "read_file_slice"]
