# Connect an assistant

End users need the operator's MCP URL and their Google account. The server operator handles Google project/API/OAuth setup. Use `https://YOUR_MCP_DOMAIN/mcp` for hosted assistants; loopback URLs are useful only for clients that can reach your local machine.

## Codex

Codex supports remote Streamable HTTP MCP servers and OAuth. Add the hosted server and authenticate:

```sh
codex mcp add google-health --url https://YOUR_MCP_DOMAIN/mcp
codex mcp login google-health
```

Complete assistant consent and Google sign-in in the browser, then ask Codex to check the Health connection. Adding the URL does not create a Google Cloud project for the end user. [Official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

## Claude and Claude Code

In Claude, add a custom connector with the public MCP URL and follow the detected OAuth flow. Claude's remote connectors originate from Anthropic's cloud, including when used from Claude Desktop; a server running only at your Mac's loopback address is not reachable by that mechanism. [Claude remote connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp).

For Claude Code:

```sh
claude mcp add --transport http google-health https://YOUR_MCP_DOMAIN/mcp
```

Use Claude Code's `/mcp` interface to authenticate. Verify the callback against the server's redirect allowlist. [Claude Code MCP](https://code.claude.com/docs/en/mcp).

## Grok

Open [grok.com/connectors](https://grok.com/connectors), choose **New Connector → Custom**, enter the hosted MCP URL, and complete authentication. Grok discovers the server's tools. [Grok custom connectors](https://docs.x.ai/grok/connectors).

## Grok Bot

Grok Bot supports custom MCP servers, including Remote HTTPS and Command connections. Use a Remote HTTPS connection for this service, supply the hosted `/mcp` URL, and use the Google OAuth sign-in flow rather than sharing a Google token or a bot-wide health credential. Grok Bot's plugin/connector setup is separate from a server implementation; inspect the available connection UI and its actual callback URI for your account. [Grok Bot MCP support](https://docs.x.ai/grok-bot/team-bots), [connected apps](https://docs.x.ai/grok-bot/computer-and-apps).

Keep a health connector personal, or require each person to sign in independently. A shared fixed bearer credential would represent one person's health access, not the current teammate's identity.

## Custom xAI API application

xAI's Responses API supports remote MCP tools. After your application completes this server's OAuth flow **for the current user**, pass that user's server-issued MCP access credential:

```json
{
  "type": "mcp",
  "server_url": "https://YOUR_MCP_DOMAIN/mcp",
  "server_label": "google-health",
  "authorization": "CURRENT_USER_MCP_ACCESS_TOKEN",
  "allowed_tools": ["get_connection_status", "get_metric_history"]
}
```

Do not put a Google access/refresh token or a shared operator token here. This is a conceptual tools-array entry; model selection and the user's OAuth lifecycle belong to the client application. [xAI remote MCP tools](https://docs.x.ai/developers/tools/remote-mcp).

## Muse

The service supplies an MCP endpoint, OAuth registration/discovery, English tool documentation and read-only classifications suitable for a connector submission. Muse has its own functional, security, legal and end-to-end review before directory distribution. Hosting this server does not approve or list a Muse connector. Provide [tools.md](tools.md), [tools.json](tools.json), the hosted URL and operator-approved review credentials through Muse's submission process. [Muse connector guidelines](https://muse.ai/platform/docs).

## First-use examples

- "Check my Google Health connection and tell me which measurements I allowed."
- "Compare my recorded sleep, resting heart rate and HRV for October 6–12, using Europe/Istanbul. Tell me which days are missing."
- "Show my steps for October 12, with the unit and measurement date."
- "List the workouts and sleep stages actually recorded last week."

An assistant should call `get_connection_status`, inspect relevant metric permissions and retrieve a bounded range. Tool availability and OAuth discovery are local protocol evidence, not proof of successful connection in each external assistant. See [verification](verification.md).

For recurring morning and evening reports, use the chosen assistant's scheduler and the English [scheduled report recipes](scheduled-reports.md). Each run reads through that person's existing OAuth connection. The service does not create scheduled tasks itself.
