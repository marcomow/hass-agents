"""Patch nanobot so context-compaction notices can be turned off per channel.

Stock nanobot 0.3.5 posts "Compressing context…" / "Context compacted."
(ContextCompactionEvent) to every channel, with no setting to disable it. The
other system notices (retry/recovery status) already reach only the WebUI.

After this patch, each channel accepts a ``sendSystemMessages`` bool (default
true, i.e. stock behaviour); when false, compaction notices are dropped for
that channel. Compaction itself still runs.

Run once after ``pip install nanobot-ai``. Fails loudly if the upstream code
changed, so a nanobot bump cannot silently ship without the patch.
"""

import sys
from pathlib import Path

NANOBOT_ROOT = None
for candidate in sys.path:
    p = Path(candidate) / "nanobot"
    if (p / "channels" / "manager.py").is_file():
        NANOBOT_ROOT = p
        break

if NANOBOT_ROOT is None:
    print("[system_messages] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)


def patch(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            print(
                f"[system_messages] ERROR: expected 1 match in {path.name}, found {count}:\n{old}",
                file=sys.stderr,
            )
            sys.exit(1)
        text = text.replace(old, new)
    path.write_text(text)
    print(f"[system_messages] patched {path.relative_to(NANOBOT_ROOT.parent)}")


patch(
    NANOBOT_ROOT / "channels" / "manager.py",
    [
        (
            "from nanobot.bus.queue import MessageBus\n",
            "from nanobot.bus.queue import MessageBus\n"
            "from nanobot.events import ContextCompactionEvent\n",
        ),
        # Let the per-channel override also be written as camelCase in JSON.
        (
            '    "show_reasoning": "showReasoning",\n',
            '    "show_reasoning": "showReasoning",\n'
            '    "send_system_messages": "sendSystemMessages",\n',
        ),
        # Resolve the flag when each channel is built (default: stock behaviour).
        (
            "        channel.show_reasoning = self._resolve_bool_override(\n"
            '            section, "show_reasoning", self.config.channels.show_reasoning,\n'
            "        )\n",
            "        channel.show_reasoning = self._resolve_bool_override(\n"
            '            section, "show_reasoning", self.config.channels.show_reasoning,\n'
            "        )\n"
            "        channel.send_system_messages = self._resolve_bool_override(\n"
            '            section, "send_system_messages", True,\n'
            "        )\n",
        ),
        # Drop compaction notices for channels that opted out.
        (
            "                if isinstance(event, RetryWaitEvent):\n"
            "                    continue\n",
            "                if isinstance(event, RetryWaitEvent):\n"
            "                    continue\n"
            "\n"
            "                if isinstance(event, ContextCompactionEvent):\n"
            "                    target = self.channels.get(msg.channel)\n"
            '                    if target is not None and not getattr(target, "send_system_messages", True):\n'
            "                        continue\n",
        ),
    ],
)
