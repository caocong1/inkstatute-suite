"""Entry point: ``python -m admin_web_ui``."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from admin_console_api.api import handle_admin_get, handle_admin_put
    from admin_console_api.feedback import ThreadSafeFeedbackQueue
    from admin_console_api.probe import handle_config_probe
    from admin_console_api.process_supervisor import ProcessSupervisor
    from admin_web_ui.server import AdminWebUiServer
    from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
    from conversation_read_view.reports_aggregator import ReportsAggregator
    from feedback_service.queue import build_pending_feedback_queue, load_jsonl_records
    from inkstatute_operator_config import OperatorConfigStore
    from platform_runtime.feature_flags import RuntimeFeatureDisabledError, RuntimeFeatureFlags
except ImportError:
    # Allow running directly from the repo without an editable install.
    _repo = Path(__file__).resolve().parents[4]
    for _base in (_repo / "packages", _repo / "services"):
        if _base.is_dir():
            for _sub in _base.iterdir():
                _src = _sub / "src"
                if _src.is_dir() and str(_src) not in sys.path:
                    sys.path.append(str(_src))
    from admin_console_api.api import handle_admin_get, handle_admin_put
    from admin_console_api.feedback import ThreadSafeFeedbackQueue
    from admin_console_api.probe import handle_config_probe
    from admin_console_api.process_supervisor import ProcessSupervisor
    from admin_web_ui.server import AdminWebUiServer
    from conversation_read_view.read_model import build_read_model, load_records_from_jsonl
    from conversation_read_view.reports_aggregator import ReportsAggregator
    from feedback_service.queue import build_pending_feedback_queue, load_jsonl_records
    from inkstatute_operator_config import OperatorConfigStore
    from platform_runtime.feature_flags import RuntimeFeatureDisabledError, RuntimeFeatureFlags


def _build_read_model(contract_log_path: str | None) -> Any:
    if not contract_log_path:
        return build_read_model([])
    path = Path(contract_log_path)
    if not path.is_file():
        return build_read_model([])
    records = load_records_from_jsonl(path)
    return build_read_model(records)


def _build_feedback_queue(feedback_path: str | None) -> Any:
    if not feedback_path:
        return ThreadSafeFeedbackQueue()
    path = Path(feedback_path)
    if not path.is_file():
        return ThreadSafeFeedbackQueue()
    records = load_jsonl_records(path)
    return ThreadSafeFeedbackQueue(build_pending_feedback_queue(records))


def create_server(env: dict[str, str] | None = None) -> ThreadingHTTPServer:
    """Create a configured ``ThreadingHTTPServer`` for the admin web UI."""
    source = env if env is not None else os.environ
    feature_flags = RuntimeFeatureFlags.from_env(source)
    feature_flags.require_enabled("admin_web_ui_enabled")

    host = source.get("ADMIN_WEB_UI_HOST", "127.0.0.1")
    try:
        port = int(source.get("ADMIN_WEB_UI_PORT", "8080"))
    except ValueError:
        port = 8080

    rbac_secret = source.get("RBAC_TOKEN_SECRET") or None
    config_path = source.get("INKSTATUTE_OPERATOR_CONFIG_PATH") or None
    config_store = OperatorConfigStore(config_path)

    contract_log_path = source.get("INKSTATUTE_CONTRACT_LOG_PATH") or None
    read_model = _build_read_model(contract_log_path)
    reports_aggregator = ReportsAggregator(contract_log_path, env=source)

    feedback_path = source.get("INKSTATUTE_FEEDBACK_QUEUE_PATH") or None
    feedback_queue = _build_feedback_queue(feedback_path)

    process_supervisor = ProcessSupervisor(env=source, config_store=config_store)
    process_supervisor.reconcile_on_startup()

    httpd = ThreadingHTTPServer((host, port), AdminWebUiServer)
    httpd.feature_flags = feature_flags
    httpd.env = dict(source)
    httpd.rbac_secret = rbac_secret
    httpd.read_model = read_model
    httpd.feedback_queue = feedback_queue
    httpd.config_store = config_store
    httpd.process_supervisor = process_supervisor
    httpd.reports_aggregator = reports_aggregator
    httpd.handle_admin_get = handle_admin_get
    httpd.handle_admin_put = handle_admin_put
    httpd.handle_config_probe = handle_config_probe

    _original_shutdown = httpd.shutdown

    def _shutdown() -> None:
        process_supervisor.shutdown_all()
        _original_shutdown()

    httpd.shutdown = _shutdown  # type: ignore[assignment]
    return httpd


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="InkStatute Admin Web UI")
    parser.add_argument("--host", default=None, help="bind host (default: env or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default: env or 8080)")
    return parser.parse_args()


def main() -> None:
    """Create a threaded admin web UI server and serve until signalled."""
    args = _parse_args()
    if args.host is not None:
        os.environ["ADMIN_WEB_UI_HOST"] = args.host
    if args.port is not None:
        os.environ["ADMIN_WEB_UI_PORT"] = str(args.port)

    try:
        httpd = create_server()
    except RuntimeFeatureDisabledError as exc:
        print(f"admin_web_ui: {exc}", file=sys.stderr)
        sys.exit(1)

    def _shutdown(_signum: int, _frame: Any) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    with httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    main()
