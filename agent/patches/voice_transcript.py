"""Patch nanobot so Telegram voice messages get their transcript posted as text.

With the environment variable ``NANOBOT_VOICE_TRANSCRIPTS=1`` (add-on option
``telegram_voice_transcripts``), every voice/audio message that reaches the
agent and is transcribed gets the transcript posted by the bot as a quoted
reply to the voice message, in the same chat/topic, without notification.
The transcript gets the same reactions as the voice message (👀 while the
turn runs, then cleared or the NOTED emoji) - group_listen.py handles the end.

This happens in the channel, before and independently of the agent turn, so:
  * the transcript is always posted, even when the turn ends in NOTED,
    NO_REPLY or an error;
  * the agent never needs the message tool for it - nanobot suppresses a turn's
    final reply once the message tool has sent to the same chat, so a model-made
    summary used to swallow NOTED / SAY: / normal answers;
  * the agent then acts on the content exactly as for a text message.

Messages dropped earlier (not allowed, or unaddressed under the "mention"
policy) are not transcribed. Run once after ``pip install nanobot-ai`` and
after group_listen.py. Fails loudly if the upstream code changed.
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
    print("[voice_transcript] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)

path = NANOBOT_ROOT / "channels" / "telegram" / "runtime.py"
text = path.read_text()

REPLACEMENTS = [
    # Post the transcript as a quoted reply and give it the 👀 "processing" reaction.
    (
        "        media_paths.extend(current_media_paths)\n"
        "        content_parts.extend(current_media_parts)\n"
        "        if current_media_paths:\n",
        "        media_paths.extend(current_media_paths)\n"
        "        content_parts.extend(current_media_parts)\n"
        "        _vt_ids: list[int] = []\n"
        "        if (\n"
        "            __import__('os').environ.get('NANOBOT_VOICE_TRANSCRIPTS') == '1'\n"
        "            and (getattr(message, 'voice', None) or getattr(message, 'audio', None))\n"
        "        ):\n"
        "            for _vt_part in current_media_parts:\n"
        "                if _vt_part.startswith('[transcription: ') and _vt_part.endswith(']'):\n"
        "                    _vt_text = _vt_part[len('[transcription: '):-1].strip()\n"
        "                    if _vt_text:\n"
        "                        if len(_vt_text) > 4000:\n"
        "                            _vt_text = _vt_text[:4000] + '…'\n"
        "                        try:\n"
        "                            _vt_msg = await message.reply_text(\n"
        "                                '🎙 ' + _vt_text,\n"
        "                                do_quote=True,\n"
        "                                disable_notification=True,\n"
        "                            )\n"
        "                            _vt_ids.append(_vt_msg.message_id)\n"
        "                            await self._add_reaction(\n"
        "                                str(message.chat_id), _vt_msg.message_id, self.config.react_emoji\n"
        "                            )\n"
        "                        except Exception as _vt_e:\n"
        "                            self.logger.warning('voice transcript post failed: {}', _vt_e)\n"
        "        if current_media_paths:\n",
    ),
    # Hand the transcript ids to the send path (group_listen clears / reacts on them).
    (
        "        metadata = self._build_message_metadata(message, user)\n",
        "        metadata = self._build_message_metadata(message, user)\n"
        "        if _vt_ids:\n"
        "            metadata['_gl_extra_reaction_ids'] = _vt_ids\n",
    ),
]

for old, new in REPLACEMENTS:
    count = text.count(old)
    if count != 1:
        print(f"[voice_transcript] ERROR: expected 1 match in {path.name}, found {count}:\n{old}", file=sys.stderr)
        sys.exit(1)
    text = text.replace(old, new)
path.write_text(text)
print(f"[voice_transcript] patched {path.relative_to(NANOBOT_ROOT.parent)}")
