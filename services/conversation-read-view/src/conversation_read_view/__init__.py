"""Read-only operator views derived from InkStatute V2 contract logs."""

from .api import handle_get, parse_query_string
from .audit import AUDIT_EVENT_TYPES, TRACE_FIELD_ALLOWLIST, handle_audit_get
from .export import (
    CONVERSATION_CSV_COLUMNS,
    TASK_CSV_COLUMNS,
    csv_metadata,
    export_csv,
    export_json,
)
from .log_reader import LogReader
from .models import (
    ConversationTurnView,
    ConversationView,
    EventReference,
    ReadModelIssue,
    TaskView,
)
from .pagination import (
    clamp_limit,
    decode_cursor,
    encode_cursor,
    resolve_max_result_limit,
    slice_page,
)
from .privacy import find_forbidden_key_path, find_forbidden_raw_payload_path, scrub_contract_payload
from .read_model import ContractLogReadModel, build_read_model, load_records_from_jsonl
from .reports_aggregator import ReportsAggregator
from .tenant_read_model import TenantScopedContractLogReadModel

__all__ = [
    "AUDIT_EVENT_TYPES",
    "CONVERSATION_CSV_COLUMNS",
    "ContractLogReadModel",
    "ConversationTurnView",
    "ConversationView",
    "EventReference",
    "LogReader",
    "ReadModelIssue",
    "ReportsAggregator",
    "TASK_CSV_COLUMNS",
    "TRACE_FIELD_ALLOWLIST",
    "TaskView",
    "TenantScopedContractLogReadModel",
    "build_read_model",
    "clamp_limit",
    "csv_metadata",
    "decode_cursor",
    "encode_cursor",
    "export_csv",
    "export_json",
    "find_forbidden_key_path",
    "find_forbidden_raw_payload_path",
    "handle_audit_get",
    "handle_get",
    "load_records_from_jsonl",
    "parse_query_string",
    "resolve_max_result_limit",
    "scrub_contract_payload",
    "slice_page",
]
