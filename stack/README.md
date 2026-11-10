# Family agents stack (portable)

Carson (nanobot), Yuvomi and the Cloudflare tunnel as one Docker Compose
project that runs the same way on a VPS, a mini PC, a Raspberry Pi or an
arm64 phone. It uses the same images as the Home Assistant add-ons
(`../agent` and [yuvomi-ha](https://github.com/marcomow/yuvomi-ha)), built on
the host, so nothing has to be published to a registry.

## What lives where

| Path | Contents |
|---|---|
| `.env` | All secrets and settings (agent + Yuvomi options, tunnel token, HA URL). Never committed. |
| `data/agents/` | Each agent's workspace (SOUL.md, memory, skills, cron jobs) and `.nanobot-<name>/` (config, sessions, WebUI state). |
| `data/yuvomi/` | `yuvomi.db` (encrypted with `db_encryption_key`), session secret, custom modules. |
| `data/yuvomi-share/` | Yuvomi documents and its nightly backups. |

`.env` + `data/` are the whole install. Everything else comes from Git.

## Rules

- **Only one host runs a given stack at a time.** Two copies fight over the
  Telegram bot, and two tunnel connectors split family.kolombo.lv between
  two databases. The move scripts stop the old host first.
- The `db_encryption_key` in the Yuvomi options must always travel with
  `data/yuvomi/yuvomi.db`; without it the database is unreadable.

## First start on a host

```sh
git clone -b portable-stack https://github.com/marcomow/hass-agents
cd hass-agents/stack
cp .env.example .env            # fill it in
scripts/encode-options.sh agents.json yuvomi.json >> .env
docker compose up -d --build
```

In the agent options, the Yuvomi MCP server URL is `http://yuvomi:3000/mcp`,
and `HA_MCP_URL` points at Home Assistant's `/api/mcp` on a URL this host can
reach.

## Move to another host

```sh
# old host
scripts/export.sh                     # stops the stack, writes family-agents-<date>.tar.gz
# copy the archive to the new host, clone this repo there, then:
scripts/import.sh family-agents-<date>.tar.gz
```

The tunnel is token-based, so family.kolombo.lv follows the stack with no DNS
change. Delete the archive afterwards: it contains every secret.

## Profiles

`COMPOSE_PROFILES` in `.env` picks what runs: `yuvomi`, `agents`, `tunnel`.
A test deploy leaves out `tunnel` and keeps Telegram tokens out of the agent
options, so it can run alongside the live instance.
