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

Reply protocol (all Telegram chats, both policies):
  * a final reply of exactly ``NOTED`` sends no message; the bot reacts 👌 to
    the user's message instead (a quiet "done");
  * a final reply of exactly ``NO_REPLY`` sends nothing;
  * for an unaddressed group message the reply is dropped UNLESS it is
    ``NOTED`` (-> 👌) or starts with ``SAY:`` (the rest is posted - used to
    confirm or ask when the agent is unsure). Silence is the default.

If a message that addresses the bot arrives while an unaddressed turn in the
same chat is still running, nanobot injects it into that turn; once the turn
has actually read it in, the turn counts as addressed, so the reply to the
@mention is not lost, and the 👀 on the @mention is cleared (NOTED reacts 👌
on the @mention). A mention that arrives too late to be merged is re-queued
by nanobot as its own turn instead. A leading SAY: is stripped from any
group reply, addressed or not.

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
    "[Overheard group message, not addressed to you. If it holds a clear decision or "
    "commitment (a task, a date, something to buy), file it and answer exactly NOTED. "
    "If you are unsure what was meant, answer SAY: followed by one short question. "
    "Otherwise answer exactly NO_REPLY.]"
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

# --- 1b. Telegram send: turn NOTED into a 👌 reaction, drop NO_REPLY, and clear
#         the 👀 left on @mentions that were merged into this turn.
patch(
    NANOBOT_ROOT / "channels" / "telegram" / "runtime.py",
    [
        (
            "        if progress_event is None:\n"
            "            self._stop_typing(msg.chat_id)\n"
            '            if reply_to_message_id := msg.metadata.get("message_id"):\n'
            "                with suppress(ValueError):\n"
            "                    await self._remove_reaction(msg.chat_id, int(reply_to_message_id))\n",
            "        if progress_event is None:\n"
            "            self._stop_typing(msg.chat_id)\n"
            '            if reply_to_message_id := msg.metadata.get("message_id"):\n'
            "                with suppress(ValueError):\n"
            "                    await self._remove_reaction(msg.chat_id, int(reply_to_message_id))\n"
            "            _gl_merged = [m for m in (msg.metadata.get('_gl_merged_mention_ids') or []) if m]\n"
            "            for _gl_mid in _gl_merged:\n"
            "                with suppress(ValueError):\n"
            "                    await self._remove_reaction(msg.chat_id, int(_gl_mid))\n"
            "            _gl_text = (msg.content or '').strip().upper()\n"
            "            if _gl_text in ('NOTED', 'NO_REPLY') and not msg.media:\n"
            "                _gl_target = _gl_merged[-1] if _gl_merged else msg.metadata.get('message_id')\n"
            "                if _gl_text == 'NOTED' and _gl_target:\n"
            "                    with suppress(ValueError):\n"
            "                        await self._add_reaction(\n"
            "                            msg.chat_id, int(_gl_target), '\U0001F44C'\n"
            "                        )\n"
            "                return\n",
        ),
    ],
)

# --- 2. Agent loop: decide what an unaddressed group turn may send.
patch(
    NANOBOT_ROOT / "agent" / "loop.py",
    [
        # Record @mentions actually merged into a running turn (keyed by turn id).
        # Recording at merge time, not at queue time, matters: a mention that
        # arrives too late is re-published as its own turn and must not make
        # the overheard turn count as addressed.
        (
            "                followup_id = metadata.get(PENDING_FOLLOWUP_ID_KEY)\n"
            "                if isinstance(followup_id, str) and followup_id:\n"
            "                    row[PENDING_FOLLOWUP_ID_KEY] = followup_id\n"
            "                return row\n",
            "                followup_id = metadata.get(PENDING_FOLLOWUP_ID_KEY)\n"
            "                if isinstance(followup_id, str) and followup_id:\n"
            "                    row[PENDING_FOLLOWUP_ID_KEY] = followup_id\n"
            "                if metadata.get('addressed_to_bot') is True and request_ctx.turn_id:\n"
            "                    self.__dict__.setdefault('_gl_merged_mentions', {}).setdefault(\n"
            "                        request_ctx.turn_id, []\n"
            "                    ).append(metadata.get('message_id'))\n"
            "                return row\n",
        ),
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
            "        _gl_merged = self.__dict__.get('_gl_merged_mentions', {}).pop(ctx.turn_id, None) or []\n"
            "        if _gl_merged:\n"
            "            # Lets Telegram clear the 👀 on those mentions and react on them.\n"
            "            ctx.delivery.delivery_message.metadata['_gl_merged_mention_ids'] = _gl_merged\n"
            "        if ctx.kind is TurnKind.USER and 'addressed_to_bot' in (ctx.msg.metadata or {}):\n"
            "            _gl_final = (ctx.final_content or '').strip()\n"
            "            _gl_say = _gl_final[:4].upper() == 'SAY:' and bool(_gl_final[4:].strip())\n"
            "            if _gl_say:\n"
            "                ctx.final_content = _gl_final[4:].strip()\n"
            "            if (\n"
            "                ctx.msg.metadata.get('addressed_to_bot') is False\n"
            "                and not _gl_merged\n"
            "                and not _gl_say\n"
            "                and _gl_final.upper() != 'NOTED'\n"
            "            ):\n"
            "                ctx.suppress_response = True\n",
        ),
    ],
)
