# Operator deployment and security

## Independent application

The service runs independently with its own dependencies, process, port and encrypted OAuth storage. It does not require a dashboard, database or native application. The Google Health adapter lives in `src/google_health_mcp/google.py`. Start with [self-hosting](self-hosting.md).

```mermaid
sequenceDiagram
    participant User
    participant Assistant
    participant MCP as Google Health MCP MCP
    participant Google as Google OAuth / Health
    User->>Assistant: Add the hosted MCP URL
    Assistant->>MCP: Discover/register OAuth client; start S256 authorization
    MCP->>User: Confirm assistant connection
    User->>Google: Sign in and choose read permissions
    Google->>MCP: Authorization code at /auth/callback
    MCP->>Google: Exchange code using operator credentials and independent PKCE
    MCP->>Assistant: Server-issued code, then MCP credentials
    Assistant->>MCP: Authenticated health tool request
    MCP->>Google: Read users/me using this request's Google authorization
    Google->>MCP: Recorded health data
    MCP->>Assistant: Structured data, coverage and units
```

FastMCP's Google OAuth proxy bridges Google's operator-registered Web client with MCP client registration/discovery. It validates Google access-token identity, scopes, expiry and operator OAuth audience, mints separate MCP reference tokens, and maintains encrypted upstream credentials. The server never accepts a raw Google token as an MCP credential. [Google provider](https://gofastmcp.com/integrations/google), [OAuth proxy](https://gofastmcp.com/servers/auth/oauth-proxy).

## Google configuration

The operator enables Google Health API and owns the OAuth consent screen and Web application client. End users authorize their own Google accounts; no end-user Google project or CLI is part of this flow. [Google Health setup](https://developers.google.com/health/setup).

The server requests `openid` for account identity, plus:

```text
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
https://www.googleapis.com/auth/googlehealth.sleep.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.nutrition.readonly
```

The health scopes are requested up front but are not all mandatory. Google can return granular consent; authorization accepts the required identity scope, and tools check the actual granted health scopes individually. Sign-in without any health scope reports `missing_permission` and performs no Health API request. No write, location, email or profile permission is requested. [Google Health scopes](https://developers.google.com/health/scopes).

Register the public URL plus `/auth/callback` as a Google redirect. This is the **upstream Google callback**, not an assistant's callback. Keep the backend's existing callback if reusing the operator client. `access_type=offline` and explicit consent allow server-side refresh; Google testing-mode grant limits still apply. [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server).

The Google account must be linked in the Google Health mobile app before health data is available. The connection-status tool verifies `/v4/users/me/identity`. Google OAuth approval by itself is not a verified Health identity. [Health identity](https://developers.google.com/health/reference/rest/v4/users/getIdentity).

Publishing an external Google consent screen, verification of requested scopes and any required assessment are operator responsibilities. Local server or protocol checks do not establish Google approval, unrestricted public access or successful external-assistant connections.

## Configuration

| Variable | Purpose |
| --- | --- |
| `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_ID` | Operator's Google Web OAuth client ID |
| `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_SECRET` | Operator's Google client secret |
| `GOOGLE_HEALTH_MCP_STORAGE_ENCRYPTION_KEY` | Independent Fernet key for OAuth storage |
| `GOOGLE_HEALTH_MCP_TOKEN_SIGNING_KEY` | At least 32 random characters; stable MCP token signing key |
| `GOOGLE_HEALTH_MCP_PUBLIC_BASE_URL` | Public HTTPS origin, without `/mcp` or any path |
| `GOOGLE_HEALTH_MCP_PRIVACY_POLICY_URL` | Operator's own HTTPS policy, linked in health-data sharing consent |
| `GOOGLE_HEALTH_MCP_HOST` | Process bind address; Docker sets `0.0.0.0` |
| `GOOGLE_HEALTH_MCP_PORT` | Host process/published Compose port; default `8001` |
| `GOOGLE_HEALTH_MCP_DATA_DIR` | Private persistent OAuth store; Docker uses `/data/oauth` |
| `GOOGLE_HEALTH_MCP_ALLOWED_CLIENT_REDIRECT_URIS` | JSON list of approved assistant callback patterns |

Public HTTP origins and wildcard redirect hosts are rejected. Development HTTP is restricted to loopback origins. The shipped redirect allowlist covers loopback native clients and fixed `claude.ai`, `chatgpt.com`, `grok.com`, and `muse.ai` hosts. Verify the actual callback of each target client and narrow patterns for deployment; add other fixed HTTPS callback hosts deliberately. Do not replace the list with a universal wildcard.

Built-in assistant consent remains enabled and binds Google callbacks to the browser that approved the connection. Host and Origin checks protect the HTTP application. Upstream Google authorization does not receive MCP's `resource` parameter; server-issued MCP tokens are still bound to this server's resource audience.

## HTTPS with the optional proxy

Point the domain's DNS to the host. Set these in the private `.env`:

```dotenv
GOOGLE_HEALTH_MCP_PUBLIC_BASE_URL=https://YOUR_MCP_DOMAIN
GOOGLE_HEALTH_MCP_DOMAIN=YOUR_MCP_DOMAIN
```

Register `https://YOUR_MCP_DOMAIN/auth/callback` in Google, then run from the repository root:

```sh
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

The overlay is an optional independent Caddy proxy. If the host already serves HTTPS on ports 80/443, add a virtual host to that proxy instead of trying to bind a second proxy on those ports. Route the full domain to the MCP service so OAuth discovery, consent, callback and token paths work as well as `/mcp`. Preserve the original public Host header. Do not enable URL/query/body access logging on OAuth or health requests.

The container health check tests process readiness; it makes no Google request. Local operation and tests do not publish DNS, obtain Google approval or connect any external account.

## Isolation, storage and disconnect

All health calls use the authenticated request's upstream token and the fixed Google `users/me` path. The service stores no health history, health snapshots or shared health-result cache. Provider records are fetched on demand and returned to the selected assistant. The assistant's own processing/retention rules remain separate from this service.

Fernet encrypts client registrations, OAuth transactions, codes, token mappings and upstream credentials before they enter the persistent disk store. The private directory is mode `0700`. Searchable disk-cache metadata, traffic metadata and backups still require normal host protection. `.env` is private and excluded from Git and Docker context. Both keys and the OAuth volume must survive restarts.

MCP access expiry follows Google's access-token lifetime by default. MCP refresh references have a fallback maximum of 30 days; upstream revocation or expiry remains authoritative. Google testing-mode refresh tokens may expire sooner. Refresh tokens rotate at the MCP layer; renewed Google credentials stay private.

Disconnect the connector in the assistant and revoke the application's access in the Google account's third-party connections to invalidate Google authorization. The current service does not advertise an RFC 7009 revocation endpoint or automatically revoke the Google grant when an assistant removes a connector. Stored references expire according to their TTL; encrypted disk-cache cleanup and backup deletion are operator-managed. Removing the entire MCP OAuth volume invalidates all connector grants, so it is not a per-user disconnect procedure.

Keep OAuth storage and both keys in restricted, encrypted backups. Rotating keys or removing the volume requires users to reconnect. Place rate limits and abuse protection in front of public authorization/registration endpoints before public operation. Scale this disk-backed release as one process on one host; multi-process or multi-host OAuth concurrency requires shared transactional storage and a separate validation pass.
