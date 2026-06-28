# InkStatute WeCom Service

This package contains dependency-light primitives for the InkStatute-owned V2 WeCom service boundary.

It owns ordinary lawyer-user callback receipt, ACK behavior, sanitized callback normalization, outbound send envelope construction, feedback callback receipt, and assistant output policy. It does not call live WeCom, Hermes, databases, queues, or runtime secret stores in repo tests.

Hermes lawfirm is an agent backend behind the adapter boundary. Hermes gateway, operator UI, update, command, help, debug, and lifecycle notices must not be sent directly to ordinary WeCom users.
