"use strict";

const $ = (id) => document.getElementById(id);
let mode = "hosted";
let config = { hostedMcpUrl: null, hostedStatus: "pending", hostedMessage: "Hosted access is being prepared. Self-hosting is available now." };
const help = {
  codex: "Add the remote server with the Codex CLI, then use codex mcp login to authorize in your browser.",
  "claude-code": "Add an HTTP server in Claude Code, then use /mcp to finish browser authorization.",
  cursor: "Add the remote URL in Cursor's MCP settings. Use its connection flow to finish Google authorization.",
  grok: "Add the URL in your assistant's custom MCP connector settings. A prompt can guide you; it cannot replace the connector UI."
};

function validEndpoint(value) {
  try {
    const url = new URL(value);
    const loopback = ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
    if ((url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) || url.username || url.password || url.search || url.hash || !/^\/mcp\/?$/.test(url.pathname)) return null;
    return url.href.replace(/\/$/, "");
  } catch { return null; }
}

function setupPrompt(client, endpoint) {
  const instructions = {
    codex: `Use the Codex CLI to add an HTTP MCP server named google-health at ${endpoint} (codex mcp add google-health --url '${endpoint}'), then run codex mcp login google-health.`,
    "claude-code": `Use claude mcp add --transport http --scope user google-health '${endpoint}'. Then guide me to /mcp in Claude Code to authenticate.`,
    cursor: `Add a remote MCP server named google-health in my personal Cursor MCP settings with this configuration, merging with existing entries: ${JSON.stringify({ mcpServers: { "google-health": { url: endpoint } } }, null, 2)}. Guide me through the MCP connection UI.`,
    grok: `Guide me to add ${endpoint} as a custom remote HTTP MCP connector in this assistant's settings. If this assistant cannot configure connectors from chat, give me the manual steps instead of claiming it is connected.`
  };
  return `Connect my assistant to the unofficial, read-only Google Health MCP server at ${endpoint}.\n\n${instructions[client]}\n\nPreserve my other MCP connections. If google-health already exists, verify its URL before changing it. Use per-user OAuth and let me finish consent and Google sign-in in my browser. Never ask for my Google password, tokens, or Cloud credentials.\n\nAfter authorization, call get_connection_status and list_health_metrics to verify my Health account link and granted permissions. Report missing permissions or errors accurately. Do not retrieve health measurements until I ask.`;
}

function refresh() {
  $("hosted-mode").setAttribute("aria-pressed", String(mode === "hosted"));
  $("self-mode").setAttribute("aria-pressed", String(mode === "self"));
  $("hosted-info").hidden = mode !== "hosted";
  $("self-info").hidden = mode !== "self";
  $("availability").textContent = config.hostedMessage;
  $("hosted-endpoint").textContent = config.hostedMcpUrl || "Endpoint will be published when ready.";
  const endpoint = validEndpoint(mode === "hosted" ? config.hostedMcpUrl : $("server-url").value.trim());
  const usable = Boolean(endpoint) && (mode === "self" || ["available", "pilot"].includes(config.hostedStatus));
  $("copy-prompt").disabled = !usable;
  $("copy-url").disabled = !usable;
  $("client-instructions").textContent = help[$("client").value];
  $("prompt-preview").value = usable ? setupPrompt($("client").value, endpoint) : mode === "hosted" ? "The hosted connection is being prepared. Choose your own server to generate a setup prompt for an existing endpoint." : "Enter a valid HTTPS endpoint ending in /mcp. Local HTTP is allowed only for loopback addresses.";
  $("copy-feedback").textContent = "";
}

async function copyText(text, button) {
  const label = button.textContent;
  try {
    await navigator.clipboard.writeText(text);
    $("copy-feedback").textContent = "Copied to clipboard.";
    button.textContent = "Copied ✓";
    setTimeout(() => { button.textContent = label; }, 1800);
  } catch {
    $("prompt-preview").value = text;
    document.querySelector(".prompt-details").open = true;
    $("prompt-preview").focus();
    $("prompt-preview").select();
    $("copy-feedback").textContent = "Clipboard access is unavailable. The text is selected below; copy it manually.";
  }
}

$("hosted-mode").addEventListener("click", () => { mode = "hosted"; refresh(); });
$("self-mode").addEventListener("click", () => { mode = "self"; refresh(); });
$("client").addEventListener("change", refresh);
$("server-url").addEventListener("input", refresh);
$("copy-prompt").addEventListener("click", () => copyText($("prompt-preview").value, $("copy-prompt")));
$("copy-url").addEventListener("click", () => copyText(validEndpoint(mode === "hosted" ? config.hostedMcpUrl : $("server-url").value), $("copy-url")));
const examples = {
  sleep: "Use my connected Google Health MCP to review last night's recorded sleep against the preceding seven days. Confirm my time zone, preserve missing data and units, and distinguish personal baseline changes from clinical reference ranges.",
  activity: "Use my connected Google Health MCP to review today's activity against the goals I've given you. Confirm my time zone, compare recorded values with my recent baseline, identify missing or delayed data, and avoid clinical classifications without appropriate sources."
};
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => copyText(examples[button.dataset.example], button)));
refresh();
fetch("config.json", { cache: "no-cache" }).then((response) => {
  if (!response.ok) throw new Error("Configuration unavailable");
  return response.json();
}).then((data) => {
  if (typeof data.hostedMessage !== "string" || !["pending", "pilot", "available"].includes(data.hostedStatus)) throw new Error("Invalid public configuration");
  config = data;
  refresh();
}).catch(() => { refresh(); });
