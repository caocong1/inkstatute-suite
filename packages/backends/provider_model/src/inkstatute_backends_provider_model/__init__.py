"""Provider model backend adapter prototype package for the InkStatute platform runtime."""

from .adapter import ProviderModelBackendAdapter, ProviderModelExecResult, ProviderModelRunner
from .config import ProviderModelBackendConfig
from .manifest import build_provider_model_manifest, provider_model_prototype_capabilities
from .openai_runner import (
    FakeOpenAITransport,
    OpenAIClientRunner,
    OpenAITransport,
    parse_openai_response,
)
from .probe import (
    ProviderModelCapabilityProbe,
    ProviderModelProbeIssue,
    ProviderModelProbeReport,
    ProviderModelProbeTransport,
)

__all__ = [
    "FakeOpenAITransport",
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
    "build_provider_model_manifest",
    "parse_openai_response",
    "provider_model_prototype_capabilities",
]
