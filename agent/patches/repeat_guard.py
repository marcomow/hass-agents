"""Patch nanobot so an agent stuck repeating the same tool call is told to stop.

Stock nanobot 0.3.5 lets a model call the same tool with the same arguments
over and over until max_tool_iterations (default 200) is reached. A weak model
that keeps sending a malformed call (e.g. empty path parameters) burns the
whole budget on one failing request.

After this patch, the runner counts consecutive iterations whose tool calls are
identical (same tool names, same arguments). From the third identical round on,
a short note is appended to the last tool result telling the model it is
looping and must stop calling tools and report the problem. The iteration cap
(``maxToolIterations``, set per agent by run.sh) still bounds the worst case.

Run once after ``pip install nanobot-ai``. Fails loudly if the upstream code
changed, so a nanobot bump cannot silently ship without the patch.
"""

import sys
from pathlib import Path

NANOBOT_ROOT = None
for candidate in sys.path:
    p = Path(candidate) / "nanobot"
    if (p / "agent" / "runner.py").is_file():
        NANOBOT_ROOT = p
        break

if NANOBOT_ROOT is None:
    print("[repeat_guard] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)


def patch(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            print(
                f"[repeat_guard] ERROR: expected 1 match in {path.name}, found {count}:\n{old}",
                file=sys.stderr,
            )
            sys.exit(1)
        text = text.replace(old, new)
    path.write_text(text)
    print(f"[repeat_guard] patched {path.relative_to(NANOBOT_ROOT.parent)}")


REPEAT_NOTE = (
    "\\n\\n[loop guard] You have made this exact same tool call {n} times in a row "
    "with the same arguments. Repeating it will not change the result. Stop calling "
    "tools now and reply to the user in one line saying what failed."
)

patch(
    NANOBOT_ROOT / "agent" / "runner.py",
    [
        # Per-run state, next to the other per-turn counters.
        (
            "        workspace_violation_counts: dict[str, int] = {}\n",
            "        workspace_violation_counts: dict[str, int] = {}\n"
            "        _rg_last_sig: tuple | None = None  # [hass-agents] repeat guard\n"
            "        _rg_count = 0\n",
        ),
        # After each tool round: compare this round's calls with the previous one.
        (
            "                tool_events.extend(new_events)\n",
            "                tool_events.extend(new_events)\n"
            "                # [hass-agents] repeat guard\n"
            "                import json as _rg_json\n"
            "                _rg_sig = tuple(\n"
            "                    (tc.name, _rg_json.dumps(tc.arguments, sort_keys=True, default=str))\n"
            "                    for tc in response.tool_calls\n"
            "                )\n"
            "                _rg_count = _rg_count + 1 if _rg_sig == _rg_last_sig else 1\n"
            "                _rg_last_sig = _rg_sig\n"
            "                if _rg_count >= 3:\n"
            "                    logger.warning(\n"
            "                        \"Repeat guard: identical tool calls {} times in a row for {}\",\n"
            "                        _rg_count,\n"
            "                        spec.session_key or \"default\",\n"
            "                    )\n",
        ),
        # Append the note to the last tool result of a repeated round.
        (
            "                checkpoint_model_messages = (\n",
            "                if (\n"
            "                    _rg_count >= 3\n"
            "                    and completed_tool_results\n"
            "                    and isinstance(completed_tool_results[-1].get(\"content\"), str)\n"
            "                ):\n"
            f"                    completed_tool_results[-1][\"content\"] += \"{REPEAT_NOTE}\".format(n=_rg_count)\n"
            "                checkpoint_model_messages = (\n",
        ),
    ],
)
