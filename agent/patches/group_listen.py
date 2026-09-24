"""Patch nanobot so a Telegram group can be "listened to" quietly.

Stock nanobot 0.3.5 offers two Telegram group policies:
  * "mention" (default): only messages that @mention the bot or reply to it
    reach the agent - everything else in the group is dropped.
  * "open": every message reaches the agent AND the agent replies to every one.

Neither fits a family group, where the butler should read everything, file what
matters (tasks, dates, things to buy), but only speak when it is addressed.

After this patch, groupPolicy "open" means "listen quietly":
  * every group message from an allowed sender reaches the agent;
  * messages that do not @mention the bot or reply to it are tagged
    (metadata ``addressed_to_bot = False`` plus a short note prepended to the
    text), get no typing indicator or reaction, and their final reply is
    suppressed - the turn still runs, so tools (e.g. creating a task) work;
  * messages that do address the bot behave exactly as before.

Private chats and the "mention" policy are unchanged.

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
    print("[group_listen] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)

UNADDRESSED_NOTE = (
    "[Group message not addressed to you. Do not reply. If it contains something "
    "actionable for the family (a task, a date, something to buy, a decision), "
    "file it silently; otherwise do nothing.]"
)


def patch(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            print(
                f"[group_listen] ERROR: expected 1 match in {path.name}, found {count}:\n{old}",
                file=sys.stderr,
            )
            sys.exit(1)
        text = text.replace(old, new)
    path.write_text(text)
    print(f"[group_listen] patched {path.relative_to(NANOBOT_ROOT.parent)}")


# --- 1. Telegram channel: accept every group message, tag the unaddressed ones.
patch(
    NANOBOT_ROOT / "channels" / "telegram" / "runtime.py",
    [
        # The helper now answers "is this addressed to the bot?" regardless of policy.
        (
            '        if message.chat.type == "private" or self.config.group_policy == "open":\n'
            "            return True\n",
            '        if message.chat.type == "private":\n'
            "            return True\n",
        ),
        # Drop unaddressed messages only under the "mention" policy.
        (
            "        if not await self._is_group_message_for_bot(message):\n"
            "            return\n",
            "        addressed = await self._is_group_message_for_bot(message)\n"
            '        if not addressed and self.config.group_policy != "open":\n'
            "            return\n",
        ),
        # Tag the message for the agent loop and the model.
        (
            "        metadata = self._build_message_metadata(message, user)\n"
            "        session_key = self._derive_topic_session_key(message)\n",
            "        metadata = self._build_message_metadata(message, user)\n"
            '        metadata["addressed_to_bot"] = addressed\n'
            "        if not addressed:\n"
            f"            content = {UNADDRESSED_NOTE!r} + \"\\n\" + content\n"
            "        session_key = self._derive_topic_session_key(message)\n",
        ),
        # No typing indicator or reaction for messages the bot will not answer.
        (
            "                self._start_typing(str_chat_id)\n"
            "                await self._add_reaction(str_chat_id, message.message_id, self.config.react_emoji)\n",
            "                if addressed:\n"
            "                    self._start_typing(str_chat_id)\n"
            "                    await self._add_reaction(str_chat_id, message.message_id, self.config.react_emoji)\n",
        ),
        (
            "        # Start typing indicator before processing\n"
            "        self._start_typing(str_chat_id)\n"
            "        await self._add_reaction(str_chat_id, message.message_id, self.config.react_emoji)\n",
            "        # Start typing indicator before processing\n"
            "        if addressed:\n"
            "            self._start_typing(str_chat_id)\n"
            "            await self._add_reaction(str_chat_id, message.message_id, self.config.react_emoji)\n",
        ),
    ],
)

# --- 2. Agent loop: never deliver the final reply to an unaddressed group message.
patch(
    NANOBOT_ROOT / "agent" / "loop.py",
    [
        (
            "    async def _prepare_outbound(self, ctx: TurnContext) -> None:\n"
            "        ctx.delivery.record_stop_reason(\n"
            "            ctx.stop_reason,\n"
            "            failure_error_kind=ctx.failure_error_kind,\n"
            "        )\n",
            "    async def _prepare_outbound(self, ctx: TurnContext) -> None:\n"
            "        ctx.delivery.record_stop_reason(\n"
            "            ctx.stop_reason,\n"
            "            failure_error_kind=ctx.failure_error_kind,\n"
            "        )\n"
            "        if (\n"
            "            ctx.kind is TurnKind.USER\n"
            '            and (ctx.msg.metadata or {}).get("addressed_to_bot") is False\n'
            "        ):\n"
            "            ctx.suppress_response = True\n",
        ),
    ],
)
