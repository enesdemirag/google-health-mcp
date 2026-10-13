from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SCOPE_PREFIX = "https://www.googleapis.com/auth/googlehealth."
HEALTH_SCOPES = [
    f"{SCOPE_PREFIX}{group}.readonly"
    for group in ("activity_and_fitness", "sleep", "health_metrics_and_measurements", "nutrition")
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOOGLE_HEALTH_MCP_", env_file=".env", extra="ignore")

    google_client_id: str = Field(min_length=1)
    google_client_secret: SecretStr
    storage_encryption_key: SecretStr
    token_signing_key: SecretStr
    public_base_url: str = "http://127.0.0.1:8001"
    privacy_policy_url: str | None = None
    host: str = "127.0.0.1"
    port: int = Field(default=8001, ge=1, le=65535)
    data_dir: Path = Path(".local/oauth")
    allowed_client_redirect_uris: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:*/*",
            "http://localhost:*/*",
            "https://claude.ai/*",
            "https://chatgpt.com/*",
            "https://grok.com/*",
            "https://muse.ai/*",
        ]
    )

    @model_validator(mode="after")
    def validate_configuration(self):
        self.public_base_url = self.public_base_url.rstrip("/")
        url = urlsplit(self.public_base_url)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.path
            or url.query
            or url.fragment
        ):
            raise ValueError("The public base URL must be an HTTP(S) origin without a path or credentials.")
        if url.scheme == "http" and url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                "Public deployments require HTTPS. HTTP is allowed only for loopback development."
            )
        if self.privacy_policy_url:
            privacy = urlsplit(self.privacy_policy_url)
            if (
                privacy.scheme not in {"http", "https"}
                or not privacy.hostname
                or privacy.username
                or privacy.password
                or (privacy.scheme == "http" and privacy.hostname not in {"127.0.0.1", "localhost", "::1"})
            ):
                raise ValueError("The privacy policy URL must use HTTPS or loopback HTTP.")
        if not self.google_client_secret.get_secret_value().strip():
            raise ValueError("An operator-owned Google Web OAuth client secret is required.")
        if len(self.token_signing_key.get_secret_value()) < 32:
            raise ValueError("The token signing key must contain at least 32 random characters.")
        try:
            Fernet(self.storage_encryption_key.get_secret_value().encode())
        except (ValueError, TypeError):
            raise ValueError("The storage encryption key must be a valid Fernet key.") from None
        if not self.allowed_client_redirect_uris:
            raise ValueError("At least one approved MCP client redirect URI pattern is required.")
        for pattern in self.allowed_client_redirect_uris:
            redirect = urlsplit(pattern)
            if (
                redirect.scheme not in {"http", "https"}
                or not redirect.hostname
                or any(char in redirect.hostname for char in "*?[")
                or redirect.username
                or redirect.password
                or redirect.fragment
                or (redirect.scheme == "http" and redirect.hostname not in {"localhost", "127.0.0.1", "::1"})
            ):
                raise ValueError("Redirect patterns must use a fixed HTTPS host or a loopback HTTP host.")
        return self

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.public_base_url}/auth/callback"
