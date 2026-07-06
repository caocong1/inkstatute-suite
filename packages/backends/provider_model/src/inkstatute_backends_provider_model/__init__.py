"""Provider model backend adapter prototype package for the InkStatute platform runtime."""

from .adapter import (
    ProviderModelBackendAdapter,
    ProviderModelExecResult,
    ProviderModelRunner,
    ProviderModelStreamDelta,
    StreamingProviderModelRunner,
)
from .config import ProviderModelBackendConfig
from .manifest import build_provider_model_manifest, provider_model_prototype_capabilities
from .openai_runner import (
    FakeOpenAITransport,
    FakeStreamingProviderModelRunner,
    OpenAIClientRunner,
    OpenAITransport,
    parse_openai_response,
    parse_sse_deltas,
)
from .probe import (
    ProviderModelCapabilityProbe,
    ProviderModelProbeIssue,
    ProviderModelProbeReport,
    ProviderModelProbeTransport,
)

__all__ = [
    "FakeOpenAITransport",
    "FakeStreamingProviderModelRunner",
    "OpenAIClientRunner",
    "OpenAITransport",
    "ProviderModelBackendAdapter",
    "ProviderModelBackendConfig",
    "ProviderModelCapabilityProbe",
    "ProviderModelExecResult",
    "ProviderModelProbeIssue",
    "ProviderModelProbeReport",
    "ProviderModelProbeTransport",
    "ProviderModelRunner",
    "ProviderModelStreamDelta",
    "StreamingProviderModelRunner",
    "build_provider_model_manifest",
    "parse_openai_response",
    "parse_sse_deltas",
    "provider_model_prototype_capabilities",
]
