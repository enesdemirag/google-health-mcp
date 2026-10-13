# Verification

The tests use synthetic Google responses and do not prove a live Google account connection, completed assistant sign-in or Google approval.

## Automated checks

On 2026-10-14, all 52 tests passed, along with lint, formatting, compilation and `git diff --check`. Run the [development commands](../README.md#development) to repeat them.

The tests cover:

- OAuth discovery, client registration, anonymous request rejection and S256 PKCE for both OAuth flows.
- Consent disclosure, same-origin form policy, rejection of null and foreign origins, CSRF protection, browser binding and callback or code replay rejection.
- Rejection of unapproved callbacks, write scopes, raw Google tokens and tokens for another client audience.
- Cursor web and desktop OAuth flows, with rejection of other paths, lookalike hosts and non-loopback HTTP callbacks.
- Encrypted storage across server instances, refresh token rotation and concurrent calls from two separate users.
- Partial consent, missing values, units, sleep and workout parsing, date validation and query limits.
- Pagination, 14-day query chunks, repeated cursors, bounded retries and errors instead of partial success.
- Personal baselines, minimum recorded-day coverage, zero and Celsius handling, prompt dates and user-supplied goals.
- Private setup files, preservation of existing keys, rejection of Desktop clients, read-only tool annotations and schemas.

Production code has no synthetic-data mode. The exported catalog has seven tools with input and output schemas.

## Docker and website checks

These checks were recorded on 2026-10-13.

```sh
docker build -t google-health-mcp:local .
```

The image built with locked dependencies. A temporary container used test credentials and temporary OAuth storage. It ran as a non-root user with a read-only filesystem. `/healthz` returned readiness, OAuth discovery returned the configured MCP URL, and an anonymous `/mcp` request returned `401`. The container was removed without contacting Google or changing other application services.

Compose configuration passed. The `setup` command created a private `0600` `.env` with fresh keys and no Google credentials. Normal Compose operation starts `mcp`, and the optional HTTPS configuration adds Caddy.

The website loaded the HealPot logo and local fonts at desktop and 390-pixel mobile widths without horizontal overflow. Self-host mode generated the expected Codex prompt. When clipboard access failed, the page selected the prompt for manual copying. Automatic clipboard access was not verified. The site labels hosted access as a pilot while Google verification is incomplete.

## Live account checks

Before claiming a live connection works:

1. Configure real Web OAuth credentials and persistent keys. Register the exact `/auth/callback` URL without removing callbacks used by other apps.
2. Confirm that the assistant can reach the HTTPS server and that its callback is allowed.
3. Sign in, grant Health permissions and check that `get_connection_status` returns `connected`.
4. Read a measurement you know exists and check its source, date and unit.
5. Test a second account, partial consent, refresh and Google-side revocation. Confirm that each account can read only its own records.

Repeat these checks for each target assistant. [Client documentation](clients.md) describes supported connection methods. This implementation has not completed live connections with those services in this verification run. Muse listing and Google app approval need their own reviews.
