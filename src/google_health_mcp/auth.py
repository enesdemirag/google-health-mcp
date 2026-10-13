from cryptography.fernet import Fernet
from fastmcp.server.auth.providers.google import GoogleProvider
from key_value.aio.stores.disk import DiskStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from google_health_mcp.config import HEALTH_SCOPES, Settings
from google_health_mcp.consent import simplify_consent_page


class HealthGoogleProvider(GoogleProvider):
    """Request health permissions up front while accepting granular Google consent."""

    privacy_policy_url: str | None = None

    def get_challenge_scopes(self, required_scopes: list[str] | None = None) -> list[str]:
        return self.scopes_supported if required_scopes is None else required_scopes

    async def _show_consent_page(self, request: Request) -> HTMLResponse | RedirectResponse:
        response = await super()._show_consent_page(request)
        marker = b'<form id="consentForm"'
        if isinstance(response, HTMLResponse) and marker in response.body:
            # Keep the browser's Origin on the form POST without sending the
            # consent transaction URL to Google or other external sites.
            response.headers["Referrer-Policy"] = "same-origin"
            response.body = simplify_consent_page(response.body.decode(), self.privacy_policy_url).encode()
            response.headers["content-length"] = str(len(response.body))
        return response


def build_auth(settings: Settings) -> HealthGoogleProvider:
    settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    settings.data_dir.chmod(0o700)
    storage = FernetEncryptionWrapper(
        key_value=DiskStore(directory=settings.data_dir),
        fernet=Fernet(settings.storage_encryption_key.get_secret_value().encode()),
    )
    provider = HealthGoogleProvider(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret.get_secret_value(),
        base_url=settings.public_base_url,
        redirect_path="/auth/callback",
        required_scopes=["openid"],
        valid_scopes=["openid", *HEALTH_SCOPES],
        allowed_client_redirect_uris=settings.allowed_client_redirect_uris,
        client_storage=storage,
        jwt_signing_key=settings.token_signing_key.get_secret_value().encode(),
        require_authorization_consent=True,
        forward_resource=False,
        token_expiry_threshold_seconds=60,
        fallback_refresh_token_expiry_seconds=30 * 24 * 60 * 60,
        extra_authorize_params={"access_type": "offline", "prompt": "consent select_account"},
    )
    provider.privacy_policy_url = settings.privacy_policy_url
    return provider
