"""Patch nanobot so the agent can post into a Telegram forum topic.

Stock nanobot 0.3.5 names a topic conversation ``telegram:<chat_id>:topic:<thread_id>``
(its session key), so a model asked to "post in the X topic" naturally calls the
``message`` tool with ``chat_id="<chat_id>:topic:<thread_id>"``. The Telegram
channel then does ``int(msg.chat_id)``, logs "Invalid chat_id" and drops the
message - while the tool has already told the model "Message sent". A bare
``<chat_id>`` without the thread lands in the group's General topic instead.

After this patch:
  * the Telegram channel accepts ``<chat_id>:topic:<thread_id>`` as a target
    and posts into that topic (``message_thread_id``);
  * the ``message`` tool validates Telegram targets before queueing them and
    returns an error for anything that is not ``<chat_id>`` or
    ``<chat_id>:topic:<thread_id>``, so a bad address is never reported as sent;
  * the tool's ``chat_id`` description documents the topic form.

Run once after ``pip install nanobot-ai``. Fails loudly if the upstream code
changed, so a nanobot bump cannot silently ship without the patch.
"""

import sys
from pathlib import Path

NANOBOT_ROOT = None
for candidate in sys.path:
    p = Path(candidate) / "nanobot"
    if (p / "channels" / "telegram" / "runtime.py").is_file():
        NANOBOT_ROOT = p
        break

if NANOBOT_ROOT is None:
    print("[topic_send] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)


def patch(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            print(
                f"[topic_send] ERROR: expected 1 match in {path.name}, found {count}:\n{old}",
                file=sys.stderr,
            )
            sys.exit(1)
        text = text.replace(old, new)
    path.write_text(text)
    print(f"[topic_send] patched {path.relative_to(NANOBOT_ROOT.parent)}")


# --- 1. Telegram channel: split "<chat_id>:topic:<thread_id>" before sending.
patch(
    NANOBOT_ROOT / "channels" / "telegram" / "runtime.py",
    [
        (
            "    async def send(self, msg: OutboundMessage) -> None:\n"
            '        """Send a message through Telegram."""\n'
            "        app = await self._wait_for_app()\n",
            "    async def send(self, msg: OutboundMessage) -> None:\n"
            '        """Send a message through Telegram."""\n'
            "        _ts_chat, _ts_sep, _ts_thread = str(msg.chat_id).partition(':topic:')\n"
            "        if _ts_sep and _ts_thread.isdigit():\n"
            "            msg.chat_id = _ts_chat\n"
            "            msg.metadata = dict(msg.metadata or {})\n"
            "            msg.metadata['message_thread_id'] = int(_ts_thread)\n"
            "        app = await self._wait_for_app()\n",
        ),
    ],
)

# --- 2. Message tool: reject Telegram targets the channel cannot deliver.
patch(
    NANOBOT_ROOT / "agent" / "tools" / "message.py",
    [
        (
            "        if not channel or not chat_id:\n"
            '            return ToolResult.error("Error: No target channel/chat specified")\n',
            "        if not channel or not chat_id:\n"
            '            return ToolResult.error("Error: No target channel/chat specified")\n'
            "\n"
            "        if channel == 'telegram':\n"
            "            import re as _ts_re\n"
            "            if not _ts_re.fullmatch(r'-?\\d+(:topic:\\d+)?', str(chat_id).strip()):\n"
            "                return ToolResult.error(\n"
            "                    f\"Error: invalid Telegram chat_id {chat_id!r}. Use the numeric chat id \"\n"
            "                    \"(e.g. -1001234567890) or, for a forum topic, \"\n"
            "                    \"'<chat_id>:topic:<thread_id>' (e.g. -1001234567890:topic:42). \"\n"
            "                    \"Nothing was sent.\"\n"
            "                )\n"
            "            chat_id = str(chat_id).strip()\n",
        ),
        (
            '            "Do not set this to the current runtime chat for a normal reply."\n',
            '            "Do not set this to the current runtime chat for a normal reply. "\n'
            "            \"Telegram forum topic: '<chat_id>:topic:<thread_id>' \"\n"
            "            \"(a bare group chat_id posts in the General topic).\"\n",
        ),
    ],
)
