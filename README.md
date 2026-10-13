# HealPot

A read-only MCP server for your Google Health data. Connect it to your AI assistant or self-host with your own Google Cloud project.

This project is unofficial and has no affiliation to Google. It uses the [MIT license](LICENSE).

## Connect your account

Open the [website](https://googlehealth.enesdemirag.com/) to check hosted availability and copy your assistant's setup prompt. Sign in with Google. No Cloud project is needed.

Your account must already be linked in the Google Health mobile app. You choose which health categories to share.

See [assistant setup](docs/clients.md) for connection commands and examples.

Agents can read [llms.txt](https://googlehealth.enesdemirag.com/llms.txt) for setup instructions.

## Run your own server

You need Docker Compose and a Google Cloud project with Google Health API enabled.

1. Clone the repository.

   ```sh
   git clone https://github.com/enesdemirag/google-health-mcp.git
   cd google-health-mcp
   ```

2. Create a Web application OAuth client and configure its consent screen and scopes. Follow [Google Cloud setup](docs/self-hosting.md#google-cloud-setup).

3. Create `.env` with new encryption and signing keys.

   ```sh
   LOCAL_UID=$(id -u) LOCAL_GID=$(id -g) docker compose --profile setup run --rm setup
   ```

   Set `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_ID` and `GOOGLE_HEALTH_MCP_GOOGLE_CLIENT_SECRET`. Keep the generated keys. Git and Docker builds exclude `.env`.

4. Register `http://127.0.0.1:8001/auth/callback` in your Google OAuth client, then start the server.

   ```sh
   docker compose up -d --build --wait
   ```

Connect a local assistant to `http://127.0.0.1:8001/mcp`. See [self-hosting](docs/self-hosting.md) for public HTTPS and Python setup.

## Tools

| Tool | What it does |
| --- | --- |
| `get_connection_status` | Checks account linking and granted permissions |
| `list_health_metrics` | Lists 17 supported metrics and their units |
| `get_metric_history` | Reads daily values and statistics |
| `get_sleep_sessions` | Reads recorded sleep sessions and stages |
| `get_workouts` | Reads recorded workouts |
| `get_health_overview` | Reads several metrics for a date range |
| `get_daily_health_context` | Compares a day with your previous recorded days |

Coverage depends on your device, recorded data and permissions. Missing readings stay missing. Personal comparisons are not clinical reference ranges.

See the [tool reference](docs/tools.md) or [generated schemas](docs/tools.json).

## Daily reports

Use the [scheduled report prompts](docs/scheduled-reports.md) for morning sleep summaries or evening goal reviews. Your assistant schedules, analyzes and delivers the report. HealPot reads the data when called.

## Privacy and hosting

HealPot encrypts Google credentials and gives assistants separate MCP tokens. It sends requested records to your assistant without storing health measurements. Your assistant's privacy and retention policies also apply.

Follow [data handling and disconnect](docs/privacy.md) to remove access.

Public operators must follow Google's verification requirements. This release supports one process on one host. See [deployment requirements](docs/deployment.md).

## Development

Use Python 3.12 or 3.13 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked --python 3.12
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
uv run --locked python -m compileall -q src
```

Tests use synthetic Google responses. See [verification](docs/verification.md) for coverage and live checks. The CLI has `--describe` for configuration and `--export-tools` for schemas.

The GitHub Pages website lives in `site/`. Keep credentials out of `site/config.json`.

See [contributing](CONTRIBUTING.md) and [security reporting](SECURITY.md). Never include health records or credentials in issues or pull requests.
