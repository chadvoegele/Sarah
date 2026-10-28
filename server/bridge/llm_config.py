"""Explicit OpenAI-compatible endpoint; provider secrets never reach the device."""
import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = 'http://127.0.0.1:8012/v1'
    model: str = 'ggml-org/Qwen3.8-27B-GGUF:Q4_K_M'
    api_key: str = field(default='', repr=False)

    def __post_init__(self):
        try:
            url = urlsplit(self.base_url)
            host = url.hostname
            _ = url.port  # Validate malformed/out-of-range ports.
        except ValueError:
            raise ValueError('Invalid SARAH_LLM_BASE_URL') from None
        try:
            loopback = host == 'localhost' or ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
        if (not url.hostname or url.scheme not in ('http', 'https') or
                (url.scheme == 'http' and not loopback) or url.username is not None or
                url.password is not None or url.query or url.fragment or
                any(c.isspace() or ord(c) < 32 for c in self.base_url)):
            raise ValueError('SARAH_LLM_BASE_URL requires HTTPS (HTTP allowed on loopback only), no credentials/query/fragment')
        object.__setattr__(self, 'base_url', self.base_url.rstrip('/'))
        if not self.model.strip() or len(self.model) > 256:
            raise ValueError('SARAH_LLM_MODEL must be a nonempty model ID')
        if len(self.api_key) > 8192 or any(ord(c) < 32 or ord(c) > 126 for c in self.api_key):
            raise ValueError('Invalid LLM API token')

    @classmethod
    def from_env(cls):
        token = os.getenv('SARAH_LLM_API_KEY', '')
        token_file = os.getenv('SARAH_LLM_API_KEY_FILE', '')
        if token and token_file:
            raise ValueError('Set only one of SARAH_LLM_API_KEY or SARAH_LLM_API_KEY_FILE')
        if token_file:
            token = Path(token_file).expanduser().read_text().strip()
        return cls(base_url=os.getenv('SARAH_LLM_BASE_URL', cls.base_url),
                   model=os.getenv('SARAH_LLM_MODEL', cls.model), api_key=token)
