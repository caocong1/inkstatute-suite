"""Entry point: ``python -m admin_console_api``."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from typing import Any

from admin_console_api.server import create_server
from platform_runtime.feature_flags import RuntimeFeatureDisabledError


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="InkStatute Admin Console API")
    parser.add_argument("--host", default=None, help="bind host (default: env or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default: env or 8081)")
    return parser.parse_args()


def main() -> None:
    """Create a threaded admin console API server and serve until signalled."""
    args = _parse_args()
    if args.host is not None:
        os.environ["ADMIN_CONSOLE_API_HOST"] = args.host
    if args.port is not None:
        os.environ["ADMIN_CONSOLE_API_PORT"] = str(args.port)

    try:
        httpd = create_server()
    except RuntimeFeatureDisabledError as exc:
        print(f"admin_console_api: {exc}", file=sys.stderr)
        sys.exit(1)

    def _shutdown(_signum: int, _frame: Any) -> None:
        # shutdown() must not run on the signal handler thread or it deadlocks
        # serve_forever().
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    with httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
