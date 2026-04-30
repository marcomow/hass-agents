#!/usr/bin/env bash
set -e

OPTIONS_PATH=/data/options.json
BASE_PORT=18790

echo "[agent] Generating configs from Home Assistant options..."
python3 - << 'PYEOF'
import json
import os
import sys
import urllib.request
import urllib.error

OPTIONS_PATH = "/data/options.json"
BASE_PORT    = 18790

try:
    with open(OPTIONS_PATH) as f:
        opts = json.load(f)
except Exception as e:
    print(f"[agent] ERROR: Could not read options: {e}", file=sys.stderr)
    sys.exit(1)

timezone           = opts.get("timezone", "UTC").strip()
search_provider    = opts.get("web_search_provider", "duckduckgo").strip()
search_api_key     = opts.get("web_search_api_key", "").strip()
global_mcp_servers = []

# Home Assistant integration (opt-in): expose HA's built-in MCP Server to agents.
# Requires the "MCP Server" integration enabled in Home Assistant. The add-on
# uses the Supervisor-provided token to call HA's API at http://supervisor/core
# unless an explicit url/token override is given.
ha_opts = opts.get("home_assistant") or {}
if ha_opts.get("enabled"):
    ha_url_override = (ha_opts.get("url") or "").strip()
    ha_url   = ha_url_override or "http://supervisor/core"
    ha_token = (ha_opts.get("token") or "").strip() or os.environ.get("SUPERVISOR_TOKEN", "")
    if "/mcp_server/sse" not in ha_url:
        ha_url = ha_url.rstrip("/") + "/mcp_server/sse"
    # Warn when user sets a custom (non-supervisor) URL without an explicit token.
    # The Supervisor token only authenticates through the supervisor proxy; hitting
    # the HA LAN IP directly requires a Long-Lived Access Token from the HA profile.
    if ha_url_override and not (ha_opts.get("token") or "").strip():
        print("[agent] WARNING: home_assistant.url is overridden to an external address "
              "but no token is set. The Supervisor token only works via the internal "
              "http://supervisor/core proxy. Set home_assistant.token to a Long-Lived "
              "Access Token from your HA user profile (Profile → Security → Long-lived "
              "access tokens).", file=sys.stderr)
    # Warn when a non-supervisor URL is used — the add-on container may not be able to
    # reach LAN IPs directly. The supervisor proxy is the reliable internal path.
    if ha_url_override and not ha_url_override.startswith("http://supervisor"):
        print(f"[agent] WARNING: Using custom HA URL '{ha_url}'. "
              "If the connection fails, check: (1) the port is correct (HA default is 8123), "
              "(2) this add-on's container can reach that address (try the default "
              "supervisor URL instead by clearing the home_assistant.url field).",
              file=sys.stderr)
    if not ha_token:
        print("[agent] WARNING: Home Assistant integration enabled but no token "
              "is available (SUPERVISOR_TOKEN missing and no override set).",
              file=sys.stderr)
    else:
        # Pre-flight: verify the HA MCP endpoint is reachable before writing config.
        try:
            req = urllib.request.Request(ha_url, headers={"Authorization": f"Bearer {ha_token}"})
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"[agent] WARNING: HA MCP server at {ha_url} returned HTTP {e.code} — "
                      "token rejected. For external URLs use a Long-Lived Access Token from "
                      "HA Profile → Security → Long-lived access tokens.", file=sys.stderr)
            elif e.code == 404:
                print(f"[agent] WARNING: HA MCP server at {ha_url} returned HTTP 404 — "
                      "endpoint not found. Ensure the 'Model Context Protocol Server' "
                      "integration is enabled in Home Assistant.", file=sys.stderr)
            # Other HTTP codes (e.g. 200, 405) are fine — SSE endpoints may reject
            # non-streaming GET with 405 but still work for MCP clients.
        except OSError as e:
            print(f"[agent] WARNING: Cannot reach HA MCP server at {ha_url} — {e}. "
                  "Check the URL (host, port) and that the address is reachable from "
                  "this add-on's container.", file=sys.stderr)
        global_mcp_servers.append({
            "name":    "home_assistant",
            "url":     ha_url,
            "api_key": ha_token,
        })
        print(f"[agent] Home Assistant MCP server enabled → {ha_url}")

for i, entry in enumerate(opts.get("mcp_servers", [])):
    if not isinstance(entry, dict):
        print(f"[agent] WARNING: MCP server entry {i} is not an object, skipping", file=sys.stderr)
        continue
    srv_name = (entry.get("name") or "").strip()
    raw_json = (entry.get("json") or "").strip()
    if not srv_name:
        print(f"[agent] WARNING: MCP server entry {i} missing name, skipping", file=sys.stderr)
        continue
    if not raw_json:
        print(f"[agent] WARNING: MCP server '{srv_name}' has no json config, skipping", file=sys.stderr)
        continue
    try:
        srv_cfg = json.loads(raw_json)
        if isinstance(srv_cfg, dict):
            srv_cfg["name"] = srv_name
            global_mcp_servers.append(srv_cfg)
        else:
            print(f"[agent] WARNING: MCP server '{srv_name}' json is not an object, skipping", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"[agent] WARNING: MCP server '{srv_name}' invalid JSON: {e}", file=sys.stderr)

agents = opts.get("agents", [])
if not agents:
    print("[agent] ERROR: No agents configured.", file=sys.stderr)
    sys.exit(1)

for idx, agent_opts in enumerate(agents):
    name = agent_opts.get("name", f"agent{idx}").strip()
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

    config_dir = f"/root/.nanobot-{safe_name}"
    workspace  = f"/data/workspace-{safe_name}"
    port       = BASE_PORT + idx

    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(workspace,  exist_ok=True)

    provider      = agent_opts.get("provider",     "openai").strip()
    api_key       = agent_opts.get("api_key",      "").strip()
    model         = agent_opts.get("model",        "gpt-4o-mini").strip()
    api_base      = agent_opts.get("api_base",     "").strip()
    groq_api_key  = agent_opts.get("groq_api_key", "").strip()
    system_prompt = agent_opts.get("system_prompt","").strip()

    config = {
        "providers": {},
        "agents": {
            "defaults": {
                "provider":  provider,
                "model":     model,
                "workspace": workspace,
                "timezone":  timezone,
            }
        },
        "gateway":  {"port": port},
        "channels": {},
    }

    # Provider credentials
    provider_cfg = {}
    if api_key:
        provider_cfg["apiKey"] = api_key
    if api_base:
        provider_cfg["apiBase"] = api_base
    config["providers"][provider] = provider_cfg

    # Groq (optional — enables voice transcription via Whisper on Telegram, plus Groq LLM models)
    if groq_api_key:
        config["providers"]["groq"] = {"apiKey": groq_api_key}

    # Telegram
    telegram_token = agent_opts.get("telegram_token", "").strip()
    if telegram_token:
        allow_from = [u for u in agent_opts.get("telegram_allow_from", []) if u]
        config["channels"]["telegram"] = {
            "enabled":   True,
            "token":     telegram_token,
            "allowFrom": allow_from if allow_from else ["*"],
        }

    # Discord
    discord_token = agent_opts.get("discord_token", "").strip()
    if discord_token:
        config["channels"]["discord"] = {
            "enabled":   True,
            "token":     discord_token,
            "allowFrom": ["*"],
        }

    # Slack
    slack_bot = agent_opts.get("slack_bot_token", "").strip()
    slack_app = agent_opts.get("slack_app_token", "").strip()
    if slack_bot and slack_app:
        config["channels"]["slack"] = {
            "enabled":  True,
            "botToken": slack_bot,
            "appToken": slack_app,
            "allowFrom": ["*"],
        }

    # Web search (shared global setting)
    if search_provider:
        search_cfg = {"provider": search_provider}
        if search_api_key:
            search_cfg["apiKey"] = search_api_key
        config["tools"] = {"web": {"search": search_cfg}}

    # MCP servers: filter global list by agent's mcp_server_names (empty = all), then merge JSON override
    allowed = [n.strip() for n in (agent_opts.get("mcp_server_names") or "").split(",") if n.strip()]
    mcp_servers = [s for s in global_mcp_servers if not allowed or s.get("name") in allowed]

    mcp_servers_json = (agent_opts.get("mcp_servers_json") or "").strip()
    if mcp_servers_json:
        try:
            per_agent = json.loads(mcp_servers_json)
            if not isinstance(per_agent, list):
                per_agent = [per_agent]
            by_name = {s.get("name", ""): i for i, s in enumerate(mcp_servers)}
            for server in per_agent:
                srv_name = server.get("name", "")
                if srv_name in by_name:
                    mcp_servers[by_name[srv_name]] = server
                else:
                    mcp_servers.append(server)
        except json.JSONDecodeError as e:
            print(f"[agent:{name}] WARNING: Invalid mcp_servers_json: {e}", file=sys.stderr)

    if mcp_servers:
        mcp_cfg = {}
        for server in mcp_servers:
            srv_name = (server.get("name") or "").strip()
            if not srv_name:
                continue
            srv = {}
            command = (server.get("command") or "").strip()
            if command:
                srv["command"] = command
            raw_args = (server.get("args") or "").strip()
            args = [a for a in raw_args.split() if a]
            if args:
                srv["args"] = args
            url = (server.get("url") or "").strip()
            if url:
                srv["url"] = url
            api_key_mcp = (server.get("api_key") or "").strip()
            if api_key_mcp:
                srv["headers"] = {"Authorization": f"Bearer {api_key_mcp}"}
            raw_tools = (server.get("enabled_tools") or "").strip()
            enabled_tools = [t.strip() for t in raw_tools.split(",") if t.strip()]
            if enabled_tools:
                srv["enabledTools"] = enabled_tools
            tool_timeout = server.get("tool_timeout")
            if tool_timeout:
                srv["toolTimeout"] = int(tool_timeout)
            mcp_cfg[srv_name] = srv
        if mcp_cfg:
            if "tools" not in config:
                config["tools"] = {}
            config["tools"]["mcpServers"] = mcp_cfg

    config_path = os.path.join(config_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    # Write system prompt to SOUL.md in the workspace (loaded as part of every system prompt)
    soul_path = os.path.join(workspace, "SOUL.md")
    if system_prompt:
        with open(soul_path, "w") as f:
            f.write(system_prompt)
        print(f"[agent:{name}] System prompt written → {soul_path}")
    elif os.path.exists(soul_path):
        os.remove(soul_path)

    channels_enabled = list(config["channels"].keys())
    print(f"[agent:{name}] Config written → {config_path}  (port {port})")
    print(f"[agent:{name}] Provider: {provider} | Model: {model} | Timezone: {timezone}")
    print(f"[agent:{name}] Channels: {channels_enabled if channels_enabled else 'none (gateway only)'}")

PYEOF

echo "[agent] Launching gateway(s)..."

# Start each agent's gateway; collect PIDs for clean shutdown
PIDS=()
while IFS=$'\t' read -r SAFE_NAME PORT; do
    CONFIG_PATH="/root/.nanobot-${SAFE_NAME}/config.json"
    echo "[agent] Starting '${SAFE_NAME}' on port ${PORT}..."
    nanobot gateway --config "${CONFIG_PATH}" &
    PIDS+=($!)
done < <(python3 - << 'PYEOF'
import json, sys

BASE_PORT = 18790
opts = json.load(open("/data/options.json"))
for idx, a in enumerate(opts.get("agents", [])):
    name = a.get("name", f"agent{idx}").strip()
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    print(f"{safe}\t{BASE_PORT + idx}")
PYEOF
)

if [ ${#PIDS[@]} -eq 0 ]; then
    echo "[agent] ERROR: No agents were started." >&2
    exit 1
fi

echo "[agent] ${#PIDS[@]} gateway(s) running. Waiting..."

# Propagate SIGTERM / SIGINT to all children
trap 'kill "${PIDS[@]}" 2>/dev/null' TERM INT

wait "${PIDS[@]}"

