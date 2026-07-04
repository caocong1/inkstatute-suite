"""InkStatute-owned short notices for ordinary WeCom users (thin shim over channel_core)."""

from __future__ import annotations

from channel_core.owned_notices import OWNED_NOTICE_TEMPLATES, NoticeKind, build_owned_notice

__all__ = ["NoticeKind", "OWNED_NOTICE_TEMPLATES", "build_owned_notice"]
