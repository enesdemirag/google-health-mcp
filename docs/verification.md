# Verification evidence

Checked locally on 2026-10-13. These checks concern the independent MCP package; they do not establish public deployment, Google verification approval, real Google consent for the new callback, or a completed connection in an external assistant.

## Automated checks

```sh
uv sync --locked --python 3.12
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv run --locked python -m compileall -q src
```

Result: **44 tests passed**. Lint, formatting and compilation passed. `git diff --check` passed.

Coverage includes:

- OAuth resource/server discovery, dynamic client registration and anonymous HTTP MCP rejection.
- Server-owned Google client/callback selection, downstream and independent upstream S256 PKCE.
- Browser consent, CSRF rejection, callback browser binding and callback/code replay rejection.
- Prominent health-data/assistant-sharing disclosure before consent, while retaining CSRF, frame protection and the content security policy.
- Rejection of unapproved callback hosts, requested write scopes, raw Google bearer tokens and tokens for a different Google OAuth audience.
- Encrypted OAuth state and credential persistence across a separate server instance.
- Rotated client refresh tokens and retention of private Google credentials on the server.
- Concurrent HTTP tool calls from two independently authorized users with distinct records.
- Partial and zero health consent, capability schemas and read-only annotations.
- ISO date/time-zone validation, unknown metric and extra user-ID input rejection before provider calls.
- Documented Google field/unit mappings, real zero versus missing values, sleep/workout parsing.
- Fourteen-day rollup chunks, pagination, repeated cursor rejection, full failure instead of partial success, and bounded retry.
- Invalid sleep/workout intervals and unavailable/unlinked provider states.
- Private operator configuration files and refusal to overwrite existing keys or accept a Desktop OAuth client as the shared Web client.
- Daily report ranges that exclude the current reading from its personal baseline, minimum recorded-day coverage, zero/Celsius percentage handling and explicit unassessed clinical ranges.
- Current local-date resolution in morning/evening prompts, per-metric consent, future-date/baseline-bound rejection and user-supplied goal handling.

OAuth and provider requests in these tests use synthetic, isolated HTTP transports. Production code has no synthetic-data mode. This suite does not send requests to a real Google account.

## Docker and Compose

```sh
docker build -t google-health-mcp:local .
```

The independent image built successfully, including locked dependency installation and a non-editable package build.

A temporary container was started with test-only operator credentials, no backend containers, a read-only root filesystem, a non-root user and temporary OAuth storage. The following actual HTTP checks passed:

- `/healthz` returned service readiness.
- `/.well-known/oauth-protected-resource/mcp` advertised the configured public MCP resource URL.
- An anonymous `/mcp` request returned `401`.
- Container inspection confirmed the `google-health-mcp` user and read-only root filesystem.

The temporary container was stopped and removed. The check did not contact Google or retain health data. No existing dashboard container, volume, database, or native application was restarted or modified.

The Compose configuration resolved successfully. Normal operation starts only `mcp`; the optional HTTPS overlay adds `caddy`. The `setup` profile provides a separate configuration container. Its documented command was exercised: it created a mode-0600 `.env` with new keys and no Google credentials, and exited. Neither deployment configuration contains or depends on other application services. Real Web OAuth credentials are still required before operation.

The website was checked in a browser at desktop and 390-pixel mobile widths, with no horizontal overflow. Self-host selection generated the expected Codex prompt. Clipboard denial revealed and selected a manual-copy fallback; automatic clipboard access was not available in that browser session. The hosted endpoint stays marked pending until deployment/account access is verified.

The exported tool catalog contains seven tools and machine-readable input/output schemas. Tool export is a schema artifact, not a completed account connection.

## Real account and external client verification

Before reporting a live connection as working:

1. Configure the operator's real Web OAuth credentials and persistent keys privately.
2. Register the exact MCP `/auth/callback` URL in Google; retain existing application callbacks.
3. Make the HTTPS endpoint reachable from the selected assistant and configure its actual callback allowlist.
4. Sign in through that assistant and grant selected Health scopes.
5. Confirm `get_connection_status` returns `connected`, then query a measurement known to exist.
6. Test a second independent Google account, partial consent, refresh and Google-side revocation.
7. Check account isolation and real source/calendar interpretation in each target assistant.

Grok, Grok Bot, Codex, Claude and Muse documentation is cited in [clients.md](clients.md). Their protocol support is documented; this implementation has not been connected to those external services in this run. Muse review/listing and Google's public-app approval remain independent processes.
