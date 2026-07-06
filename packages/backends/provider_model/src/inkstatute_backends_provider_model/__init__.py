"""Provider model backend adapter prototype package for the InkStatute platform runtime."""

from .adapter import (
    ProviderModelBackendAdapter,
    ProviderModelExecResult,
    ProviderModelRunner,
    ProviderModelStreamDelta,
    StreamingProviderModelRunner,
)
from .anthropic_runner import (
    AnthropicRunner,
    AnthropicTransport,
    FakeAnthropicTransport,
    parse_anthropic_response,
)
from .config import ProviderModelBackendConfig
from .error_normalization import normalize_provider_error, sanitize_error_message
from .manifest import build_provider_model_manifest, provider_model_prototype_capabilities
from .openai_runner import (
    FakeOpenAITransport,
    FakeStreamingProviderModelRunner,
    OpenAIClientRunner,
    OpenAITransport,
    parse_openai_response,
    parse_sse_deltas,
)
from .ollama_runner import (
    FakeOllamaTransport,
    OllamaHTTPError,
    OllamaRunner,
    OllamaTransport,
)
from .probe import (
    ProviderModelCapabilityProbe,
    ProviderModelProbeIssue,
    ProviderModelProbeReport,
    ProviderModelProbeTransport,
)

__all__ = [
    "AnthropicRunner",
    "AnthropicTransport",
    "FakeAnthropicTransport",
    "FakeOllamaTransport",
    "FakeOpenAITransport",
    "FakeStreamingProviderModelRunner",
    "OllamaHTTPError",
    "OllamaRunner",
    "OllamaTransport",
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
    "parse_anthropic_response",
    "parse_openai_response",
    "parse_sse_deltas",
    "provider_model_prototype_capabilities",
]
