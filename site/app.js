"use strict";

const $ = (id) => document.getElementById(id);
let mode = "hosted";
let config = { hostedMcpUrl: null, hostedStatus: "pending", hostedMessage: "Checking hosted availability." };
const help = {
  codex: "Use codex mcp login to finish Google sign-in in your browser.",
  "claude-code": "Use /mcp in Claude Code to finish Google sign-in.",
  cursor: "Finish Google sign-in in Cursor's MCP settings.",
  others: "Add the URL in your assistant's MCP settings and finish Google sign-in."
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
  const quotedEndpoint = "'" + endpoint.replace(/'/g, "'\\''") + "'";
  const instructions = {
    codex: `Run in my local Codex environment:\ncodex mcp add google-health --url ${quotedEndpoint}\ncodex mcp login google-health`,
    "claude-code": `Run in my local Claude Code environment:\nclaude mcp add --transport http --scope user google-health ${quotedEndpoint}\nThen use /mcp to authenticate.`,
    cursor: `Merge this entry into my personal ~/.cursor/mcp.json:\n${JSON.stringify({ mcpServers: { "google-health": { url: endpoint } } }, null, 2)}\nAuthenticate in Cursor's MCP settings.`,
    others: `Add ${endpoint} as a custom MCP connection with Streamable HTTP and OAuth. If you cannot configure the connector here, give me the manual steps.`
  };
  return `Connect my Google Health account to HealPot at ${endpoint}.\n\nPreserve my other MCP connections. If google-health already exists, check its URL before changing it.\n\n${instructions[client]}\n\nUse my own OAuth connection. Let me finish Google consent in my browser. Never ask for passwords, tokens or Cloud credentials.\n\nCall get_connection_status and list_health_metrics. Report my connection status and permissions. Read measurements only when I ask.`;
}

function refresh() {
  $("hosted-mode").setAttribute("aria-pressed", String(mode === "hosted"));
  $("self-mode").setAttribute("aria-pressed", String(mode === "self"));
  $("hosted-info").hidden = mode !== "hosted";
  $("self-info").hidden = mode !== "self";
  $("url-hint").hidden = mode !== "self";
  $("availability").textContent = mode === "hosted" ? config.hostedMessage : "";
  $("connection-status").textContent = mode === "self" ? "Your server" : { pending: "Preparing", pilot: "Hosted pilot", available: "Hosted server" }[config.hostedStatus];
  $("hosted-endpoint").textContent = config.hostedMcpUrl || "Loading endpoint...";
  const endpoint = validEndpoint(mode === "hosted" ? config.hostedMcpUrl : $("server-url").value.trim());
  const usable = Boolean(endpoint) && (mode === "self" || ["available", "pilot"].includes(config.hostedStatus));
  $("copy-prompt").disabled = !usable;
  $("copy-url").disabled = !usable;
  $("client-instructions").textContent = help[$("client").value];
  $("prompt-preview").value = usable ? setupPrompt($("client").value, endpoint) : mode === "hosted" ? "Hosted access is unavailable. Choose Your server to use your own endpoint." : "Enter an HTTPS URL ending in /mcp. Local clients can use loopback HTTP.";
  $("copy-feedback").textContent = "";
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    $("copy-feedback").textContent = "Copied.";
  } catch {
    $("prompt-preview").value = text;
    document.querySelector(".prompt-details").open = true;
    $("prompt-preview").focus();
    $("prompt-preview").select();
    $("copy-feedback").textContent = "Copy the selected text below.";
  }
}

$("hosted-mode").addEventListener("click", () => { mode = "hosted"; refresh(); });
$("self-mode").addEventListener("click", () => { mode = "self"; refresh(); });
$("client").addEventListener("change", refresh);
$("server-url").addEventListener("input", refresh);
$("copy-prompt").addEventListener("click", () => copyText($("prompt-preview").value));
$("copy-url").addEventListener("click", () => copyText(validEndpoint(mode === "hosted" ? config.hostedMcpUrl : $("server-url").value)));
const examples = {
  sleep: "Use my Google Health connection to compare last night's sleep with the preceding seven days. Confirm my time zone and show missing data. Personal baselines are not clinical reference ranges.",
  activity: "Use my Google Health connection to review today's activity against my goals. Confirm my time zone, keep units and show missing or delayed readings."
};
document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => copyText(examples[button.dataset.example])));
refresh();
fetch("config.json", { cache: "no-cache" }).then((response) => {
  if (!response.ok) throw new Error("Configuration unavailable");
  return response.json();
}).then((data) => {
  if (typeof data.hostedMessage !== "string" || !["pending", "pilot", "available"].includes(data.hostedStatus)) throw new Error("Invalid public configuration");
  config = data;
  refresh();
}).catch(() => { config.hostedMessage = "Could not check hosted availability. Use your own server or reload."; refresh(); });
