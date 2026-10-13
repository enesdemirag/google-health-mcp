# Self-hosting

Each operator uses their own Google Cloud project, Web application OAuth client, host and encryption keys. End users of that operator's server do not create projects or provide credentials.

## Google Cloud

1. Create a Cloud project or select one you administer. Enable **Google Health API**.
2. Configure Google Auth Platform for an external application. Supply accurate app information, support details, privacy policy and terms. Add your test users while the app is in Testing.
3. Create an OAuth client of type **Web application**, not Desktop or Installed application.
4. Add `openid` and these health permissions under Data Access:

   ```text
   https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
   https://www.googleapis.com/auth/googlehealth.sleep.readonly
   https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
   https://www.googleapis.com/auth/googlehealth.nutrition.readonly
   ```

5. Register `http://127.0.0.1:8001/auth/callback` for local operation, or `https://YOUR_MCP_DOMAIN/auth/callback` for HTTPS hosting. This callback belongs to the MCP server, not the assistant.

The selected account must be linked to Google Health in its mobile app. OAuth sign-in alone does not establish that link. The server checks `users.getIdentity` and handles partial/zero health consent.

Follow [Google setup](https://developers.google.com/health/setup), [scope guidance](https://developers.google.com/health/scopes) and [app verification](https://developers.google.com/health/app-verification). Testing-mode refresh tokens expire after seven days. Unverified applications have a 100-user limit; publication and security assessment requirements apply to your deployment.

## Docker configuration

```sh
git clone https://github.com/enesdemirag/google-health-mcp.git
cd google-health-mcp
LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose --profile setup run --rm setup
```

The setup container creates `.env` with fresh encryption/signing keys and mode `0600`. It refuses to overwrite a file. On Linux it runs as your host UID/GID, so the generated file belongs to you.

Edit `.env` to fill in your Web client ID and secret. Alternatively, use Python and the downloaded Web OAuth client JSON:

```sh
uv sync --locked --python 3.12
uv run --locked python scripts/configure.py \
  --google-client-json /private/path/web-client.json \
  --public-base-url https://YOUR_MCP_DOMAIN
```

Neither credentials nor `.env` are committed or included in the server image. Keep both keys and the `mcp_oauth` volume across upgrades.

```sh
docker compose up -d --build --wait
```

The service runs on `http://127.0.0.1:8001/mcp`. Its readiness endpoint is `/healthz`; readiness does not call Google. A local MCP client can reach loopback, but a cloud assistant cannot reach your computer's loopback address.

## Public HTTPS

Point your domain to the server, register its Google callback, and configure:

```dotenv
GOOGLE_HEALTH_MCP_PUBLIC_BASE_URL=https://YOUR_MCP_DOMAIN
GOOGLE_HEALTH_MCP_DOMAIN=YOUR_MCP_DOMAIN
```

If this host has no reverse proxy using ports 80/443:

```sh
docker compose -f compose.yaml -f compose.production.yaml up -d --build --wait
```

The optional Caddy container obtains TLS certificates and routes the whole origin, including OAuth discovery and callbacks. If the VPS already has a reverse proxy, use its separate virtual host instead and keep the MCP container bound to loopback. Forward the original Host header and do not enable credential/query/body logging.

Approve actual assistant callback hosts using `GOOGLE_HEALTH_MCP_ALLOWED_CLIENT_REDIRECT_URIS`. The defaults permit loopback native clients and a small set of fixed HTTPS assistant hosts; verify and narrow them for your deployment. Universal host wildcards are rejected.

The authorization flow includes a health-specific data-sharing disclosure. Before public operation, publish your operator privacy/terms information, set `GOOGLE_HEALTH_MCP_PRIVACY_POLICY_URL`, and supply a per-user credential deletion process, rate limits and any Google-required verification/security assessment. The repository does not grant Google approval.

## Upgrades and backups

Back up the OAuth volume and both keys using restricted, encrypted storage. Pull a reviewed version and rebuild without removing volumes. `docker compose down` preserves authorization; `docker compose down -v` deletes it for every connected user.

Google-side revocation remains authoritative. The current server has no public token-revocation or per-user deletion endpoint; removing a connector does not revoke its Google grant. Read [privacy and disconnect](privacy.md) before operating a shared service.

For more configuration and security details, see [deployment.md](deployment.md).
