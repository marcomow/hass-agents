# Hass Agents

A collection of Home Assistant add-ons that bring AI agents to your smart home, installable via [HACS](https://hacs.xyz).

## Add-ons

### AI Agents (powered by [nanobot](https://github.com/HKUDS/nanobot))

An ultra-lightweight personal AI agent with multi-channel support. Connect it to Telegram, Discord, or Slack and back it with any LLM — OpenRouter, OpenAI, Anthropic, DeepSeek, Ollama, or any OpenAI-compatible endpoint.

## Installation

### 1. Add this repository to HACS

1. In Home Assistant, open **HACS → ⋮ → Custom repositories**
2. Enter `https://github.com/marcomow/hass-agents` and select category **Add-ons**
3. Click **Add**

### 2. Install the add-on

1. Go to **Settings → Add-ons → Add-on Store**
2. Find **AI Agents** and click **Install**

### 3. Configure

Open the add-on **Configuration** tab and set at minimum:

| Option | Description | Default |
|---|---|---|
| `provider` | LLM provider name | `openrouter` |
| `api_key` | API key for the provider | *(empty)* |
| `model` | Model to use | `openrouter/auto` |
| `api_base` | Custom API base URL (optional) | *(empty)* |
| `timezone` | IANA timezone, e.g. `Europe/Berlin` | `UTC` |

#### Messaging channels (all optional)

| Option | Description |
|---|---|
| `telegram_token` | Bot token from @BotFather |
| `telegram_allow_from` | List of allowed Telegram user IDs (empty = all) |
| `discord_token` | Discord bot token |
| `slack_bot_token` | Slack Bot OAuth token (`xoxb-...`) |
| `slack_app_token` | Slack App-level token (`xapp-...`) |

#### Web search (optional)

| Option | Description |
|---|---|
| `web_search_provider` | `duckduckgo` (free), `brave`, `tavily`, `jina`, `searxng` |
| `web_search_api_key` | API key for Brave, Tavily, or Jina |

### 4. Start

Click **Start**. The agent gateway is available at `http://<ha-ip>:18790`.

## Provider examples

| Provider | `provider` | `model` example |
|---|---|---|
| OpenRouter (default) | `openrouter` | `openrouter/auto` |
| OpenAI | `openai` | `gpt-4o-mini` |
| Anthropic | `anthropic` | `claude-sonnet-4-5` |
| DeepSeek | `deepseek` | `deepseek-chat` |
| Ollama (local) | `ollama` | `llama3.2` |

For Ollama set `api_base` to your Ollama server URL, e.g. `http://192.168.1.10:11434`.

## Credits

The AI Agents add-on is a Home Assistant wrapper around [nanobot](https://github.com/HKUDS/nanobot) by HKUDS.