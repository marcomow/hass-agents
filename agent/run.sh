#!/usr/bin/env bash
set -e

OPTIONS_PATH=/data/options.json
BASE_PORT=18790

echo "[agent] Generating configs from Home Assistant options..."
python3 - << 'PYEOF'
import json
import os
import sys

OPTIONS_PATH = "/data/options.json"
BASE_PORT    = 18790

try:
    with open(OPTIONS_PATH) as f:
        opts = json.load(f)
except Exception as e:
    print(f"[agent] ERROR: Could not read options: {e}", file=sys.stderr)
    sys.exit(1)

timezone        = opts.get("timezone", "UTC").strip()
search_provider = opts.get("web_search_provider", "duckduckgo").strip()
search_api_key  = opts.get("web_search_api_key", "").strip()

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

