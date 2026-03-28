#!/usr/bin/env bash
set -e

OPTIONS_PATH=/data/options.json
CONFIG_DIR=/root/.nanobot
WORKSPACE=/data/workspace

echo "[agent] Creating directories..."
mkdir -p "${CONFIG_DIR}"
mkdir -p "${WORKSPACE}"

echo "[agent] Generating config from Home Assistant options..."
python3 - << 'PYEOF'
import json
import os
import sys

OPTIONS_PATH = "/data/options.json"
CONFIG_DIR   = "/root/.nanobot"
WORKSPACE    = "/data/workspace"

try:
    with open(OPTIONS_PATH) as f:
        opts = json.load(f)
except Exception as e:
    print(f"[agent] ERROR: Could not read options: {e}", file=sys.stderr)
    sys.exit(1)

provider  = opts.get("provider", "openai").strip()
api_key   = opts.get("api_key", "").strip()
model     = opts.get("model", "gpt-4o-mini").strip()
api_base  = opts.get("api_base", "").strip()
timezone  = opts.get("timezone", "UTC").strip()

config = {
    "providers": {},
    "agents": {
        "defaults": {
            "provider": provider,
            "model": model,
            "workspace": WORKSPACE,
            "timezone": timezone,
        }
    },
    "gateway": {"port": 18790},
    "channels": {},
}

# Provider
provider_cfg = {}
if api_key:
    provider_cfg["apiKey"] = api_key
if api_base:
    provider_cfg["apiBase"] = api_base
config["providers"][provider] = provider_cfg

# Telegram
telegram_token = opts.get("telegram_token", "").strip()
if telegram_token:
    allow_from = [u for u in opts.get("telegram_allow_from", []) if u]
    config["channels"]["telegram"] = {
        "enabled": True,
        "token": telegram_token,
        "allowFrom": allow_from if allow_from else ["*"],
    }

# Discord
discord_token = opts.get("discord_token", "").strip()
if discord_token:
    config["channels"]["discord"] = {
        "enabled": True,
        "token": discord_token,
        "allowFrom": ["*"],
    }

# Slack
slack_bot = opts.get("slack_bot_token", "").strip()
slack_app = opts.get("slack_app_token", "").strip()
if slack_bot and slack_app:
    config["channels"]["slack"] = {
        "enabled": True,
        "botToken": slack_bot,
        "appToken": slack_app,
        "allowFrom": ["*"],
    }

# Web search
search_provider = opts.get("web_search_provider", "duckduckgo").strip()
search_api_key  = opts.get("web_search_api_key", "").strip()
if search_provider:
    search_cfg = {"provider": search_provider}
    if search_api_key:
        search_cfg["apiKey"] = search_api_key
    config["tools"] = {"web": {"search": search_cfg}}

config_path = os.path.join(CONFIG_DIR, "config.json")
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"[agent] Config written to {config_path}")
print(f"[agent] Provider: {provider} | Model: {model} | Timezone: {timezone}")
channels_enabled = list(config["channels"].keys())
print(f"[agent] Channels enabled: {channels_enabled if channels_enabled else 'none (gateway only)'}")
PYEOF

echo "[agent] Starting gateway on port 18790..."
exec nanobot gateway

