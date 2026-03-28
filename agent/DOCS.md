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
| `mcp_servers` | No | *(empty list)* | List of MCP (Model Context Protocol) servers to connect to |

#### MCP server options

Each entry in `mcp_servers` supports the following fields:

| Option | Required | Description |
|---|---|---|
| `name` | Yes | Unique identifier for this MCP server |
| `command` | No* | Executable to run (for stdio transport, e.g. `npx`, `uvx`) |
| `args` | No | Command arguments for stdio transport |
| `url` | No* | HTTP/SSE endpoint URL (for remote MCP servers) |
| `headers` | No | List of `{key, value}` HTTP headers (e.g. `Authorization`) |
| `enabled_tools` | No | Subset of tools to register — omit or use `["*"]` for all |
| `tool_timeout` | No | Per-call timeout in seconds (default: 30) |

\* Either `command` (stdio) or `url` (HTTP) is required.

---

## Supported providers

| Provider | `provider` value | Example `model` |
|---|---|---|
| [OpenRouter](https://openrouter.ai) (default) | `openrouter` | `openrouter/auto` |
| [OpenAI](https://platform.openai.com) | `openai` | `gpt-4o-mini` |
| [Anthropic](https://www.anthropic.com) | `anthropic` | `claude-sonnet-4-5` |
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

```yaml
agents:
  - name: home-assistant
    provider: openai
    api_key: sk-...
    model: gpt-4o-mini
    telegram_token: "123456:ABC..."
    mcp_servers:
      # Stdio transport (local process)
      - name: filesystem
        command: npx
        args:
          - "-y"
          - "@modelcontextprotocol/server-filesystem"
          - "/config"
      # HTTP/SSE transport (remote server)
      - name: my-remote-mcp
        url: "https://example.com/mcp/"
        headers:
          - key: Authorization
            value: "Bearer my-secret-token"
        tool_timeout: 60
      # With tool filtering
      - name: github
        url: "https://api.githubcopilot.com/mcp/"
        headers:
          - key: Authorization
            value: "Bearer ghp_..."
        enabled_tools:
          - get_issue
          - create_issue
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
    model: claude-sonnet-4-5
    slack_bot_token: "xoxb-..."
    slack_app_token: "xapp-..."
```

---

## Support

- Source code & issues: [github.com/marcomow/hass-agents](https://github.com/marcomow/hass-agents)
- Underlying engine: [github.com/HKUDS/nanobot](https://github.com/HKUDS/nanobot)

