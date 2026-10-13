# Connect an assistant

Use the operator's public MCP URL and sign in with your own Google account. A cloud assistant cannot reach a server at your computer's loopback address.

The [website](https://googlehealth.enesdemirag.com/) has setup prompts for the hosted server or your own URL.

## Codex

```sh
codex mcp add google-health --url https://YOUR_MCP_DOMAIN/mcp
codex mcp login google-health
```

Complete consent and Google sign-in in the browser. Then ask Codex to check your Health connection. See [Codex MCP setup](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Claude

Add a custom connector with the public MCP URL and follow the OAuth flow. Remote connectors run from Anthropic's cloud, including in Claude Desktop, so they need a public endpoint. See [Claude custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

## Claude Code

```sh
claude mcp add --transport http google-health https://YOUR_MCP_DOMAIN/mcp
```

Authenticate through `/mcp` in Claude Code. The server must allow the client's callback URL. See [Claude Code MCP setup](https://code.claude.com/docs/en/mcp).

## Grok

Open [Grok connectors](https://grok.com/connectors), choose New Connector, then Custom. Enter the public MCP URL and finish authentication. See [Grok custom connectors](https://docs.x.ai/grok/connectors).

## Grok Bot

Add a Remote HTTPS MCP connection with the server's `/mcp` URL. Complete Google OAuth and check the bot's actual callback against the server's allowlist. See [Grok Bot MCP support](https://docs.x.ai/grok-bot/team-bots) and [connected apps](https://docs.x.ai/grok-bot/computer-and-apps).

Keep the connector personal or have each person sign in separately. Sharing one bearer token gives everyone access to the same person's health data.

## An xAI API application

Complete this server's OAuth flow for the current user. Then add a remote MCP entry to your Responses API tools array.

```json
{
  "type": "mcp",
  "server_url": "https://YOUR_MCP_DOMAIN/mcp",
  "server_label": "google-health",
  "authorization": "CURRENT_USER_MCP_ACCESS_TOKEN",
  "allowed_tools": ["get_connection_status", "get_metric_history"]
}
```

Use the user's server-issued MCP token, never a Google token or shared operator token. Your application handles model selection, OAuth and token refresh. See [xAI remote MCP tools](https://docs.x.ai/developers/tools/remote-mcp).

## Muse

Submit the hosted URL, [tool reference](tools.md), [tool schemas](tools.json) and operator-approved review credentials through [Muse's connector review](https://muse.ai/platform/docs). A running server does not mean Muse has approved or listed it.

## First use

Ask your assistant to check `get_connection_status`, list permitted metrics, then read a short date range.

- "Check my Google Health connection and tell me which measurements I allowed."
- "Compare my sleep for October 6 to 12 using Europe/Istanbul. Show any missing days."
- "Show my steps for October 12 with the unit and recorded date."

See [scheduled reports](scheduled-reports.md) for recurring requests. These instructions describe client support. They do not prove a completed connection with each service. Use the [live verification checklist](verification.md#live-account-checks) to test your setup.
