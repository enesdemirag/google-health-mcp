import asyncio
import base64
import hashlib
import json
import re
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlsplit

import httpx
import httpx2
import pytest
from cryptography.fernet import Fernet

from google_health_mcp.config import HEALTH_SCOPES, Settings
from google_health_mcp.server import create_server


@asynccontextmanager
async def running_app(app):
    # AnyIO's lifespan task group must enter and exit in the same task.
    started, stopped = asyncio.Event(), asyncio.Event()

    async def run():
        async with app.router.lifespan_context(app):
            started.set()
            await stopped.wait()

    task = asyncio.create_task(run())
    await asyncio.wait_for(started.wait(), timeout=10)
    try:
        yield
    finally:
        stopped.set()
        await task


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        google_client_id="operator.apps.googleusercontent.com",
        google_client_secret="operator-only-secret",
        storage_encryption_key=Fernet.generate_key().decode(),
        token_signing_key="test-signing-key-" * 4,
        public_base_url="https://mcp.example.test",
        data_dir=tmp_path / "oauth",
    )


class OAuthHarness:
    def __init__(self, settings, client, server, app, calls):
        self.settings, self.client, self.server, self.app, self.calls = settings, client, server, app, calls

    async def start(self, person="a", scopes=None, redirect_uri="http://localhost:48100/callback"):
        scopes = scopes if scopes is not None else ["openid", *HEALTH_SCOPES]
        redirect = redirect_uri
        registration = await self.client.post(
            "/register",
            json={
                "client_name": "Test assistant",
                "redirect_uris": [redirect],
                "application_type": "native",
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "scope": " ".join(scopes),
            },
        )
        assert registration.status_code == 201, registration.text
        client_id = registration.json()["client_id"]
        verifier = f"{person}-" + "v" * 64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        authorized = await self.client.get(
            "/authorize",
            params={
                "client_id": client_id,
                "redirect_uri": redirect,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": f"assistant-state-{person}",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": f"{self.settings.public_base_url}/mcp",
            },
        )
        assert authorized.status_code in {302, 303}, authorized.text
        consent_url = authorized.headers["location"]
        consent = await self.client.get(consent_url)
        assert consent.status_code == 200, consent.text
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', consent.text)[1]
        transaction = parse_qs(urlsplit(consent_url).query)["txn_id"][0]
        return {
            "client_id": client_id,
            "verifier": verifier,
            "redirect": redirect,
            "csrf": csrf,
            "transaction": transaction,
            "person": person,
        }

    async def approve(self, flow):
        approved = await self.client.post(
            "/consent",
            headers={"Origin": self.settings.public_base_url},
            data={"txn_id": flow["transaction"], "csrf_token": flow["csrf"], "action": "approve"},
        )
        assert approved.status_code in {302, 303}, approved.text
        query = parse_qs(urlsplit(approved.headers["location"]).query)
        assert query["client_id"] == [self.settings.google_client_id]
        assert query["redirect_uri"] == [self.settings.google_redirect_uri]
        assert query["code_challenge_method"] == ["S256"]
        assert query["access_type"] == ["offline"]
        assert "resource" not in query
        flow["google_state"] = query["state"][0]
        return flow

    async def callback(self, flow):
        callback = await self.client.get(
            "/auth/callback", params={"state": flow["google_state"], "code": f"code-{flow['person']}"}
        )
        assert callback.status_code == 302, callback.text
        target = urlsplit(callback.headers["location"])
        expected = urlsplit(flow["redirect"])
        assert (target.scheme, target.netloc, target.path) == (
            expected.scheme,
            expected.netloc,
            expected.path,
        )
        query = parse_qs(target.query)
        assert query["state"] == [f"assistant-state-{flow['person']}"]
        assert "google-person" not in callback.headers["location"]
        flow["code"] = query["code"][0]
        return flow

    async def exchange(self, flow, verifier=None):
        return await self.client.post(
            "/token",
            data={
                "grant_type": "authorization_code",
                "client_id": flow["client_id"],
                "code": flow["code"],
                "redirect_uri": flow["redirect"],
                "code_verifier": verifier or flow["verifier"],
            },
        )

    async def login(self, person="a", scopes=None):
        flow = await self.start(person, scopes)
        await self.approve(flow)
        await self.callback(flow)
        response = await self.exchange(flow)
        assert response.status_code == 200, response.text
        return {**flow, **response.json()}

    async def rpc(self, access_token, method, params=None):
        return await self.client.post(
            "/mcp",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-11-25",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )


@pytest.fixture
async def oauth(settings, monkeypatch):
    calls = []

    def google_response(request):
        calls.append(request)
        if request.url.path == "/token":
            data = parse_qs(request.content.decode())
            person = (data.get("code") or data.get("refresh_token"))[0].split("-")[-1]
            groups = [] if person == "none" else [HEALTH_SCOPES[1] if person == "b" else HEALTH_SCOPES[0]]
            return httpx2.Response(
                200,
                json={
                    "access_token": f"google-person-{person}",
                    "refresh_token": f"private-refresh-{person}",
                    "expires_in": 3600,
                    "scope": " ".join(["openid", *groups]),
                    "token_type": "Bearer",
                },
            )
        credential = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not credential.startswith("google-person-"):
            return httpx2.Response(401, json={"error": "invalid_token"})
        person = credential.split("-")[-1]
        if request.url.path == "/tokeninfo":
            groups = [] if person == "none" else [HEALTH_SCOPES[1] if person == "b" else HEALTH_SCOPES[0]]
            return httpx2.Response(
                200,
                json={
                    "aud": settings.google_client_id,
                    "sub": f"person-{person}",
                    "scope": " ".join(["openid", *groups]),
                    "expires_in": 3600,
                },
            )
        return httpx2.Response(200, json={"id": f"person-{person}"})

    original_client = httpx2.AsyncClient

    def upstream_client(*args, **kwargs):
        kwargs["transport"] = httpx2.MockTransport(google_response)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx2, "AsyncClient", upstream_client)

    def health_response(request):
        calls.append(request)
        credential = request.headers["Authorization"].removeprefix("Bearer ")
        if request.url.path.endswith("/identity"):
            return httpx.Response(200, json={"healthUserId": f"linked-{credential}"})
        if "/steps/" in request.url.path:
            body = json.loads(request.content)
            start = body["range"]["start"]["date"]["day"]
            end = body["range"]["end"]["date"]["day"]
            return httpx.Response(
                200,
                json={
                    "rollupDataPoints": [
                        {
                            "civilStartTime": {"date": {"year": 2026, "month": 10, "day": day}},
                            "steps": {"countSum": str(value) if credential == "google-person-a" else "99"},
                        }
                        for day, value in [(6, 5000), (7, 6000), (8, 7000), (12, 8120)]
                        if start <= day < end
                    ]
                },
            )
        return httpx.Response(200, json={"dataPoints": [], "rollupDataPoints": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(health_response)) as health_client:
        server = create_server(settings, google_client=health_client)
        app = server.http_app(
            path="/mcp",
            json_response=True,
            stateless_http=True,
            host_origin_protection=True,
            allowed_hosts=["mcp.example.test"],
            allowed_origins=[settings.public_base_url],
        )
        async with running_app(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url=settings.public_base_url,
                follow_redirects=False,
            ) as client:
                yield OAuthHarness(settings, client, server, app, calls)
