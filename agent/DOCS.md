# AI Agents

An ultra-lightweight personal AI agent add-on with multi-channel support. Connect it to **Telegram**, **Discord**, or **Slack** and back it with any LLM — OpenRouter, OpenAI, Anthropic, DeepSeek, Ollama, or any OpenAI-compatible endpoint.

Powered by [nanobot](https://github.com/HKUDS/nanobot).

---

## Configuration

### Global options

| Option | Required | Default | Description |
|---|---|---|---|
| `timezone` | Yes | `UTC` | IANA timezone string (e.g. `Europe/Berlin`) |
| `web_search_provider` | No | `duckduckgo` | Web search backend: `duckduckgo`, `brave`, `tavily`, `jina`, `searxng` |
| `web_search_api_key` | No | *(empty)* | API key for Brave, Tavily, or Jina search providers |
| `home_assistant.enabled` | No | `false` | Expose Home Assistant's built-in MCP Server to all agents |
| `home_assistant.token` | No | *(auto)* | Long-Lived Access Token — required if the default Supervisor token is rejected (HTTP 403) |

### Home Assistant integration

Disabled by default. When enabled, the add-on injects an MCP server named
`home_assistant` into every agent, letting them call Home Assistant tools
(turn on lights, query sensors, run scripts, etc.) using HA's built-in MCP
Server.

**Prerequisites:**

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**
   and add **"Model Context Protocol Server"**.
2. Configure which entities to expose to the MCP server (typically via the
   Assist exposed-entities settings).
3. In this add-on, set `home_assistant.enabled: true` and restart.

The add-on connects automatically through the internal Supervisor proxy — no
URL configuration is needed. Authentication defaults to the Supervisor token,
which works in most setups. If the add-on logs an **HTTP 403** error at
startup, the HA MCP Server integration requires a regular user token instead:

1. In HA, go to your **Profile → Security → Long-lived access tokens**.
2. Create a new token and copy it.
3. Paste it into `home_assistant.token` and restart the add-on.

To restrict the integration to specific agents, list them in each agent's
**Active MCP Servers** field (the server name is `home_assistant`).

> Note: this is the *outbound* direction (agents → HA). It is unrelated to
> Home Assistant ingress, which is the *inbound* direction (HA embedding the
> add-on's UI in the dashboard).

### MCP Servers

Add one entry per MCP server using the **MCP Servers** list. Each entry has two fields:

- **Server Name**: a unique identifier for this server (e.g. `github`, `filesystem`)
- **Server Config (JSON)**: the server's connection config as a JSON object

All configured servers are available to all agents by default (use **Active MCP Servers** per agent to restrict which ones are loaded).

Supported JSON config fields:

| Field | Required | Description |
|---|---|---|
| `command` | No* | Executable for stdio transport (e.g. `npx`, `uvx`) |
| `args` | No | Space-separated command arguments |
| `url` | No* | HTTP/SSE endpoint for a remote MCP server |
| `api_key` | No | Bearer token sent as the `Authorization` header |
| `enabled_tools` | No | Comma-separated tool names to expose — omit for all |
| `tool_timeout` | No | Per-call timeout in seconds |

\* Either `command` (stdio) or `url` (HTTP/SSE) is required per server.

### Agents

You can define **multiple independent agent instances**, each with its own model and messaging channel.

| Option | Required | Default | Description |
|---|---|---|---|
| `name` | Yes | `default` | Unique name for this agent instance |
| `provider` | Yes | `openrouter` | LLM provider name (see table below) |
| `api_key` | No | *(empty)* | API key for the chosen provider |
| `model` | Yes | `openrouter/auto` | Model identifier (see table below) |
| `api_base` | No | *(empty)* | Custom API base URL (required for Ollama and self-hosted providers) |
| `telegram_token` | No | *(empty)* | Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `telegram_allow_from` | No | *(empty list)* | Allowed Telegram user IDs — leave empty to allow everyone |
| `discord_token` | No | *(empty)* | Discord bot token |
| `slack_bot_token` | No | *(empty)* | Slack Bot OAuth token (`xoxb-…`) |
| `slack_app_token` | No | *(empty)* | Slack App-level token (`xapp-…`) |
| `mcp_server_names` | No | *(empty)* | Comma-separated names of global MCP servers to activate — leave empty to use all (e.g. `github,filesystem`) |
| `mcp_servers_json` | No | *(empty)* | Advanced: per-agent JSON overrides merged on top of global MCP Servers |

---

## Supported providers

| Provider | `provider` value | Example `model` |
|---|---|---|
| [OpenRouter](https://openrouter.ai) (default) | `openrouter` | `openrouter/auto` |
| [OpenAI](https://platform.openai.com) | `openai` | `gpt-4o-mini` |
| [Anthropic](https://www.anthropic.com) | `anthropic` | `claude-sonnet-4-6` |
| [DeepSeek](https://platform.deepseek.com) | `deepseek` | `deepseek-chat` |
| [Ollama](https://ollama.com) (local) | `ollama` | `llama3.2` |
| Any OpenAI-compatible | any name | your model ID |

> For **Ollama**, set `api_base` to your Ollama server URL, e.g. `http://192.168.1.10:11434`.

---

## Setting up messaging channels

### Telegram

1. Open Telegram and message [@BotFather](https://t.me/BotFather).
2. Send `/newbot` and follow the prompts to get your bot token.
3. Paste the token into `telegram_token`.
4. Optionally, restrict access by adding your numeric Telegram user ID(s) to `telegram_allow_from` (find yours with [@userinfobot](https://t.me/userinfobot)).

### Discord

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, create a bot and copy the token into `discord_token`.
3. Enable **Message Content Intent** under **Privileged Gateway Intents**.
4. Invite the bot to your server with at least `Send Messages` and `Read Message History` permissions.

### Slack

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app **from scratch**.
2. Under **Socket Mode**, enable it and generate an **App-level token** (`xapp-…`) — paste into `slack_app_token`.
3. Under **OAuth & Permissions**, add the `chat:write` and `channels:history` bot scopes, then install the app to your workspace and copy the **Bot User OAuth Token** (`xoxb-…`) into `slack_bot_token`.
4. Invite the bot to a channel with `/invite @your-bot-name`.

---

## Web interface

The agent gateway UI is available at:

```
http://<your-ha-ip>:18790
```

---

## MCP servers example

Add each MCP server as a separate entry in the **MCP Servers** list by pasting its JSON config:

```yaml
mcp_servers:
  - name: filesystem
    json: '{"command":"npx","args":"-y @modelcontextprotocol/server-filesystem /config"}'
  - name: my-remote-mcp
    json: '{"url":"https://example.com/mcp/","api_key":"my-secret-token","tool_timeout":60}'
  - name: github
    json: '{"url":"https://api.githubcopilot.com/mcp/","api_key":"ghp_...","enabled_tools":"get_issue,create_issue"}'

agents:
  - name: home-assistant
    provider: openai
    api_key: sk-...
    model: gpt-4o-mini
    telegram_token: "123456:ABC..."
  - name: work-bot
    provider: anthropic
    api_key: sk-ant-...
    model: claude-sonnet-4-6
    slack_bot_token: "xoxb-..."
    slack_app_token: "xapp-..."
    mcp_server_names: "github"
```

---

## Multiple agents example

```yaml
agents:
  - name: home-assistant
    provider: openai
    api_key: sk-...
    model: gpt-4o-mini
    telegram_token: "123456:ABC..."
  - name: work-bot
    provider: anthropic
    api_key: sk-ant-...
    model: claude-sonnet-4-6
    slack_bot_token: "xoxb-..."
    slack_app_token: "xapp-..."
```

---

## Support

- Source code & issues: [github.com/marcomow/hass-agents](https://github.com/marcomow/hass-agents)
- Underlying engine: [github.com/HKUDS/nanobot](https://github.com/HKUDS/nanobot)

