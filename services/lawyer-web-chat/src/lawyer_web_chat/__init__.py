"""Lawyer Web Chat — server-side rendered web chat with SSE for InkStatute V2."""

from .boundary import ChatBoundary
from .feedback import FeedbackHandler, FeedbackResult
from .history import ChatMessage, MessageHistory
from .server import CSP_HEADER, LawyerWebChatServer, handle_lawyer_chat_request
from .session import (
    COOKIE_FLAGS,
    COOKIE_NAME,
    ChatSession,
    SessionStore,
    build_set_cookie_header,
    extract_cookie,
)
from .sse import SseStream
from .upload import FileUploadHandler, UploadResult

__all__ = [
    "CSP_HEADER",
    "COOKIE_FLAGS",
    "COOKIE_NAME",
    "ChatBoundary",
    "ChatMessage",
    "ChatSession",
    "FeedbackHandler",
    "FeedbackResult",
    "FileUploadHandler",
    "LawyerWebChatServer",
    "MessageHistory",
    "SessionStore",
    "SseStream",
    "UploadResult",
    "build_set_cookie_header",
    "extract_cookie",
    "handle_lawyer_chat_request",
]
