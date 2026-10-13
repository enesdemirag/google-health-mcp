import asyncio
from urllib.parse import parse_qs

import httpx
import pytest
from fastmcp.server.auth.providers.google import GoogleTokenVerifier

from google_health_mcp.auth import build_auth
from google_health_mcp.config import HEALTH_SCOPES, Settings


async def test_oauth_discovery_and_anonymous_requests(oauth):
    metadata = await oauth.client.get("/.well-known/oauth-authorization-server")
    assert metadata.status_code == 200
    assert metadata.json()["registration_endpoint"].endswith("/register")
    assert "S256" in metadata.json()["code_challenge_methods_supported"]
    resource = await oauth.client.get("/.well-known/oauth-protected-resource/mcp")
    assert resource.json()["resource"] == f"{oauth.settings.public_base_url}/mcp"
    assert set(HEALTH_SCOPES) <= set(resource.json()["scopes_supported"])
    response = await oauth.client.post(
        "/mcp",
        headers={"Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]
    assert "googlehealth.sleep.readonly" in response.headers["www-authenticate"]
    assert (await oauth.client.get("/healthz")).json()["service"] == "google-health-mcp"


async def test_google_tokens_stay_encrypted_and_server_side(oauth):
    account = await oauth.login()
    assert account["access_token"] != "google-person-a"
    assert account["refresh_token"] != "private-refresh-a"
    for path in oauth.settings.data_dir.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            assert b"google-person-a" not in content
            assert b"private-refresh-a" not in content
    # Stable keys and persistent storage survive a separate server instance.
    restored = build_auth(oauth.settings)
    restored.set_mcp_path("/mcp")
    token = await restored.load_access_token(account["access_token"])
    assert token.subject == "person-a"
    assert token.token == "google-person-a"
    assert token.scopes == ["openid", HEALTH_SCOPES[0]]


async def test_pkce_callback_state_and_code_replay(oauth):
    flow = await oauth.start()
    await oauth.approve(flow)
    await oauth.callback(flow)
    assert (await oauth.exchange(flow, "wrong-verifier" * 5)).status_code in {400, 401}
    assert (await oauth.exchange(flow)).status_code == 200
    assert (await oauth.exchange(flow)).status_code in {400, 401}
    replay = await oauth.client.get(
        "/auth/callback", params={"state": flow["google_state"], "code": "code-a"}
    )
    assert replay.status_code in {400, 401}
    exchanged = [request for request in oauth.calls if request.url.path == "/token"]
    assert len(exchanged) == 1
    google_form = parse_qs(exchanged[0].content.decode())
    assert google_form["code_verifier"] != [flow["verifier"]]


async def test_two_simultaneous_exchanges_cannot_reuse_code(oauth):
    flow = await oauth.start()
    await oauth.approve(flow)
    await oauth.callback(flow)
    responses = await asyncio.gather(oauth.exchange(flow), oauth.exchange(flow))
    assert sum(response.status_code == 200 for response in responses) == 1
    assert sum(response.status_code in {400, 401} for response in responses) == 1


async def test_consent_requires_csrf_and_same_browser(oauth):
    flow = await oauth.start()
    bad = await oauth.client.post(
        "/consent", data={"txn_id": flow["transaction"], "csrf_token": "wrong", "action": "approve"}
    )
    assert bad.status_code in {400, 403}
    await oauth.approve(flow)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=oauth.app), base_url=oauth.settings.public_base_url
    ) as other_browser:
        callback = await other_browser.get(
            "/auth/callback", params={"state": flow["google_state"], "code": "code-a"}
        )
        assert callback.status_code == 403
    await oauth.callback(flow)


async def test_simple_consent_preserves_data_sharing_notice_and_oauth(oauth):
    flow = await oauth.start()
    page = await oauth.client.get("/consent", params={"txn_id": flow["transaction"]})
    assert page.status_code == 200
    assert page.text.index("can read your Google Health data") < page.text.index('<form id="consentForm"')
    assert "share it with its AI provider" in page.text
    assert "<strong>Test assistant</strong>" in page.text
    assert 'value="approve">Allow</button>' in page.text
    assert 'value="deny">Deny</button>' in page.text
    assert "Application Access Request" not in page.text
    assert "Advanced Details" not in page.text
    assert "Credentials will be sent to" not in page.text
    assert "csrf_token" in page.text
    assert int(page.headers["content-length"]) == len(page.content)
    assert 'http-equiv="Content-Security-Policy"' in page.text
    assert page.headers["x-frame-options"] == "DENY"
    assert page.headers["referrer-policy"] == "same-origin"
    await oauth.approve(flow)
    await oauth.callback(flow)
    assert (await oauth.exchange(flow)).status_code == 200


@pytest.mark.parametrize("origin", ["null", "https://attacker.example"])
async def test_consent_rejects_untrusted_origins_with_valid_csrf(oauth, origin):
    flow = await oauth.start()
    response = await oauth.client.post(
        "/consent",
        headers={"Origin": origin},
        data={"txn_id": flow["transaction"], "csrf_token": flow["csrf"], "action": "approve"},
    )
    assert response.status_code == 403
    assert response.text == "Forbidden Origin"


async def test_registration_rejects_unapproved_redirects_and_write_scopes(oauth):
    for body in [
        {"redirect_uris": ["https://attacker.example/callback"]},
        {
            "redirect_uris": ["https://grok.com/callback"],
            "scope": "https://www.googleapis.com/auth/googlehealth.sleep.writeonly",
        },
    ]:
        response = await oauth.client.post(
            "/register", json={"client_name": "Unapproved", "token_endpoint_auth_method": "none", **body}
        )
        assert response.status_code == 400


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "https://www.cursor.com/agents/mcp/oauth/callback",
        "http://localhost:8787/callback",
    ],
)
async def test_cursor_callback_completes_oauth(oauth, redirect_uri):
    flow = await oauth.start(redirect_uri=redirect_uri)
    await oauth.approve(flow)
    await oauth.callback(flow)
    assert (await oauth.exchange(flow)).status_code == 200


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "https://www.cursor.com/other-callback",
        "https://www.cursor.com.attacker.example/agents/mcp/oauth/callback",
        "http://www.cursor.com/agents/mcp/oauth/callback",
        "https://www.cursor.com/agents/mcp/oauth/callback/extra",
    ],
)
async def test_cursor_callback_allowlist_rejects_other_urls(oauth, redirect_uri):
    response = await oauth.client.post(
        "/register",
        json={
            "client_name": "Unapproved callback",
            "redirect_uris": [redirect_uri],
            "token_endpoint_auth_method": "none",
            "scope": "openid",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_redirect_uri"


async def test_invalid_and_raw_google_tokens_are_not_mcp_credentials(oauth):
    for token in ["invalid-token", "google-person-a"]:
        assert (await oauth.rpc(token, "tools/list")).status_code == 401


async def test_refresh_tokens_remain_private_and_are_rotated(oauth):
    account = await oauth.login()
    refreshed = await oauth.client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": account["client_id"],
            "refresh_token": account["refresh_token"],
        },
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["refresh_token"] != account["refresh_token"]
    assert "google-person-a" not in refreshed.text
    assert "private-refresh-a" not in refreshed.text
    replay = await oauth.client.post(
        "/token",
        data={
            "grant_type": "refresh_token",
            "client_id": account["client_id"],
            "refresh_token": account["refresh_token"],
        },
    )
    assert replay.status_code in {400, 401}


async def test_google_verifier_checks_operator_audience():
    import httpx2

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(
            lambda request: httpx2.Response(
                200, json={"aud": "another-app", "sub": "person-a", "scope": "openid", "expires_in": 3600}
            )
        )
    ) as client:
        verifier = GoogleTokenVerifier(required_scopes=["openid"], audience="our-app", http_client=client)
        assert await verifier.verify_token("valid-for-another-app") is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("public_base_url", "http://public.example"),
        ("public_base_url", "https://mcp.example/path"),
        ("token_signing_key", "short"),
        ("storage_encryption_key", "invalid"),
        ("google_client_secret", ""),
        ("allowed_client_redirect_uris", ["https://*/callback"]),
        ("allowed_client_redirect_uris", ["http://public.example/callback"]),
    ],
)
def test_configuration_fails_closed(settings, field, value):
    with pytest.raises(ValueError):
        Settings(_env_file=None, **{**settings.model_dump(), field: value})
