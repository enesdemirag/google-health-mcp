# HealPot — Google Health MCP (Unofficial)

An **unofficial, open-source, read-only** MCP server for Google Health. Connect your own health data to an MCP-compatible AI assistant through Google sign-in.

Not affiliated with, endorsed by, or maintained by Google. Licensed under [MIT](LICENSE).

[Website and connection prompts](https://enesdemirag.github.io/google-health-mcp/) · [Self-hosting](docs/self-hosting.md) · [Tools](docs/tools.md) · [Assistant setup](docs/clients.md)

## Choose how to connect

- **Hosted service:** the website shows the operator's endpoint and availability. Add that URL to your assistant and authorize your own Google account. You do not need a Cloud project, credentials, or this repository. If hosting is still being prepared, the website says so and does not advertise a working connection.
- **Self-host:** run this server with your own Google Cloud project and Web application OAuth client. You own the host, credentials and encrypted authorization storage. People using your server only need its MCP URL and Google sign-in.

An ordinary Google account is not enough: it must already be linked to a Google Health profile in the Google Health mobile app. The server verifies that link after authorization. Partial health permissions are supported.

## Self-host in five steps

Requirements: Docker Compose, a Google Cloud project with Google Health API enabled, and a **Web application** OAuth client. Google access and verification requirements apply independently to each operator.

1. Clone the project:

   ```sh
   git clone https://github.com/enesdemirag/google-health-mcp.git
   cd google-health-mcp
   ```

2. In your Cloud project, enable Google Health API, configure the external OAuth consent screen, add your test users, and create a Web application OAuth client. Add the four read-only scopes listed in [self-hosting](docs/self-hosting.md).
3. Create your private environment and generate independent encryption/signing keys:

   ```sh
   LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose --profile setup run --rm setup
   ```

   Edit the new `.env` and fill in `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_ID` and `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_SECRET`. Keep both generated keys. The file is ignored by Git and excluded from Docker builds.
4. Register this Google redirect URI for local use:

   ```text
   http://127.0.0.1:8001/auth/callback
   ```

   Start the server:

   ```sh
   docker compose up -d --build --wait
   ```

5. Add `http://127.0.0.1:8001/mcp` to a local MCP client and complete OAuth. For cloud assistants, deploy on a reachable HTTPS domain and register its `/auth/callback` URL instead. [HTTPS deployment](docs/self-hosting.md#public-https).

Prefer Python? Use Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --locked --python 3.12
uv run --locked python scripts/configure.py
# Fill in your Web OAuth credentials in .env.
uv run --locked google-health-mcp
```

## What assistants can read

| Tool | Purpose |
| --- | --- |
| `get_connection_status` | Verify Health account linking and granted permissions |
| `list_health_metrics` | Discover 17 supported metrics, units and aggregation rules |
| `get_metric_history` | Read daily values, coverage and descriptive statistics |
| `get_sleep_sessions` | Read available sleep sessions and stages |
| `get_workouts` | Read recorded workouts and optional measurements |
| `get_health_overview` | Read selected metrics with separate availability states |
| `get_daily_health_context` | Compare a day with the user's preceding recorded days |

Supported metrics include steps, calories, distance, sleep duration, resting heart rate, HRV, SpO₂, respiratory rate, weight and nutrition. Coverage depends on device, account, recorded data and consent. This is not every Google Health data type or proprietary score.

All descriptions, schemas, resources, prompts and documentation are English. [Full tool reference](docs/tools.md) · [Machine-readable catalog](docs/tools.json).

## Ask useful questions

- “Check my connection and tell me which measurements I allowed.”
- “Compare last night's recorded sleep with my preceding seven days, using my time zone.”
- “Review today's activity against the goals I gave you. Identify missing data.”

The assistant can schedule morning sleep summaries or evening goal reviews if its scheduler supports authenticated MCP tools. **Scheduling, AI analysis and delivery belong to the assistant.** The server reads on demand and returns descriptive comparisons; personal baselines are not clinical reference ranges. [Scheduled report recipes](docs/scheduled-reports.md).

## Data and authorization

Google access and refresh tokens stay encrypted in the operator's persistent OAuth store. Assistants receive separate MCP credentials. Every health request uses the authorized user's `users/me`; there is no shared health account or user-ID tool argument.

The server does not persist health measurements. It processes them in memory and returns requested results to the connected assistant, whose own processing and retention policies also apply. Removing a connector does not by itself revoke the Google grant. [Data handling and disconnect](docs/privacy.md).

Public hosting requires the operator's Google OAuth verification and any required security assessment. Open-source publication does not establish approval. This version uses one process on one host; it is not a shared multi-host OAuth store. [Deployment and security](docs/deployment.md).

## Development

```sh
uv sync --locked --python 3.12
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv run --locked python -m compileall -q src
```

Tests use synthetic OAuth and provider data. They do not prove a live Google connection or compatibility with every assistant. Run `google-health-mcp --describe` for non-secret configuration information and `--export-tools` for the live tool schemas. [Verification](docs/verification.md).

The website is dependency-free HTML/CSS/JavaScript in `site/`, published by GitHub Pages. Its `config.json` contains public endpoint information only; never put credentials there.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md). Do not post personal health records, OAuth credentials or `.env` files in issues or pull requests.
