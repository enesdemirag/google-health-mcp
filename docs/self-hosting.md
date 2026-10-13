# Self-hosting

Run HealPot with your own Google Cloud project, OAuth client and host. People connecting to your server only need its MCP URL and their Google account.

## Google Cloud setup

1. Create or select a project you administer. Enable Google Health API.
2. In Google Auth Platform, configure an external app with your support details, privacy policy and terms. Add test users while the app is in Testing.
3. Create an OAuth client of type Web application. Desktop clients will not work.
4. Under Data access, add `openid` and these read-only scopes.

   ```text
   https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
   https://www.googleapis.com/auth/googlehealth.sleep.readonly
   https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
   https://www.googleapis.com/auth/googlehealth.nutrition.readonly
   ```

5. Register `http://127.0.0.1:8001/auth/callback` for local use, or `https://YOUR_MCP_DOMAIN/auth/callback` for HTTPS hosting. This is the server's Google callback. Assistants have separate callbacks.

Users must link their accounts in the Google Health mobile app before connecting. They can grant some or none of the health scopes. Tools report missing permissions for categories they did not grant.

Google's [setup](https://developers.google.com/health/setup), [scopes](https://developers.google.com/health/scopes) and [verification](https://developers.google.com/health/app-verification) guides cover access requirements. Testing-mode refresh tokens expire after seven days. Unverified apps have a 100-user limit. Publishing an app does not complete verification.

## Docker setup

```sh
git clone https://github.com/enesdemirag/google-health-mcp.git
cd google-health-mcp
LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose --profile setup run --rm setup
```

The setup command creates `.env` with new encryption and signing keys and file permissions `0600`. It uses your user and group IDs and refuses to overwrite an existing file.

Set `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_ID` and `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_SECRET` in `.env`, then start the server.

```sh
docker compose up -d --build --wait
```

The MCP URL is `http://127.0.0.1:8001/mcp`. Only clients on your machine can use this loopback URL. `/healthz` checks server readiness without calling Google.

Keep both keys and the `mcp_oauth` volume across upgrades. Git and Docker builds exclude `.env`.

## Python setup

Use Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked --python 3.12
uv run --locked python scripts/configure.py
# Fill in the Web OAuth client ID and secret in .env.
uv run --locked google-health-mcp
```

To import a downloaded Web client JSON file, add `--google-client-json /private/path/web-client.json` to the configuration command. For remote hosting, also add `--public-base-url https://YOUR_MCP_DOMAIN`. Run configuration before creating `.env`, since it will not overwrite that file.

## Public HTTPS

Point your domain to the host and register `https://YOUR_MCP_DOMAIN/auth/callback` in Google. Set these values in `.env`.

```dotenv
GOOGLE_HEALTH_MCP_PUBLIC_BASE_URL=https://YOUR_MCP_DOMAIN
GOOGLE_HEALTH_MCP_DOMAIN=YOUR_MCP_DOMAIN
```

If ports 80 and 443 are free, start the optional Caddy proxy.

```sh
docker compose -f compose.yaml -f compose.production.yaml up -d --build --wait
```

Caddy obtains TLS certificates and forwards the whole domain to HealPot. If you already run a reverse proxy, add a separate virtual host there and keep the MCP port bound to loopback. Forward the original Host header and all paths, including OAuth discovery and callbacks. Disable URL, query and body logging.

Review `GOOGLE_HEALTH_MCP_ALLOWED_CLIENT_REDIRECT_URIS` against each assistant's actual callback. Allow only approved hosts. Universal host wildcards are rejected.

Before accepting other users, publish your privacy policy and terms, set `GOOGLE_HEALTH_MCP_PRIVACY_POLICY_URL`, and provide a per-user credential deletion process. Add rate limits and complete Google's required verification and security assessment. See [deployment](deployment.md) for configuration details.

## Upgrades and backups

Back up the OAuth volume and both keys in encrypted storage with restricted access. Pull a reviewed version and rebuild without deleting volumes. `docker compose down` keeps authorization data. `docker compose down -v` deletes it for every user.

The server has no per-user deletion or token-revocation endpoint. Removing a connector does not revoke its Google grant. Follow the [disconnect instructions](privacy.md#disconnect).
