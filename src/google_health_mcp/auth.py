from html import escape

from cryptography.fernet import Fernet
from fastmcp.server.auth.providers.google import GoogleProvider
from key_value.aio.stores.disk import DiskStore
from key_value.aio.wrappers.encryption import FernetEncryptionWrapper
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from google_health_mcp.config import HEALTH_SCOPES, Settings


class HealthGoogleProvider(GoogleProvider):
    """Request health permissions up front while accepting granular Google consent."""

    privacy_policy_url: str | None = None

    def get_challenge_scopes(self, required_scopes: list[str] | None = None) -> list[str]:
        return self.scopes_supported if required_scopes is None else required_scopes

    async def _show_consent_page(self, request: Request) -> HTMLResponse | RedirectResponse:
        response = await super()._show_consent_page(request)
        marker = b'<form id="consentForm"'
        if isinstance(response, HTMLResponse) and marker in response.body:
            policy = (
                f'<p><a href="{escape(self.privacy_policy_url, quote=True)}" '
                'target="_blank" rel="noopener noreferrer">Operator privacy policy and disconnect</a></p>'
                if self.privacy_policy_url
                else "<p>Ask this server's operator for their privacy and data-deletion policy.</p>"
            )
            notice = (
                '<section class="info-box" aria-label="Google Health data sharing">'
                "<h2>Google Health data sharing</h2>"
                "<p>This connection requests read access to activity and fitness, sleep, health measurements "
                "and nutrition. You choose which categories to allow on Google's consent screen.</p>"
                "<p>When you ask a health or fitness question, this server sends requested health records "
                "to the assistant shown above. That assistant or its AI provider receives those results "
                "and follows its own data policies.</p>"
                "<p>Authorization credentials are stored encrypted. Health measurements are processed "
                "in memory and are not persisted by this server. Allow Access confirms this data sharing "
                "before you continue to Google; Deny cancels the connection.</p>"
                f"{policy}</section>"
            ).encode()
            response.body = response.body.replace(marker, notice + marker, 1)
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
