"""Patch nanobot's cron tool so weak models can still create reminders.

Seen with openrouter/auto (Nov 2026): some routed models call
``cron(action="add", at=..., job_id="candele-...", limit=1)`` - the reminder
text is missing, the job label is sent as ``job_id`` (a field only meant for
remove/update/...), and ``limit`` (history only) is added. Stock nanobot
rejects the call with "message is required", the model repeats the same broken
call, and the loop guard stops it: no reminder is created.

After this patch the cron tool, for action="add" only:

* takes the reminder text from ``message`` or, failing that, from a common
  alias the model may have used (text, content, reminder, prompt, task,
  instruction, description, body, note), or from ``name``;
* treats ``job_id`` as the label (``name``) instead of an error;
* drops fields that make no sense for add (``limit``, ``include_disabled``,
  ``job_id``) and any unknown keys, so execute() never gets stray kwargs;
* when the text is still missing, returns an error that shows the exact call
  to send, built from the arguments the model already gave.

The tool description also gets a concrete add example.

Run once after ``pip install nanobot-ai``. Fails loudly if the upstream code
changed, so a nanobot bump cannot silently ship without the patch.
"""

import sys
from pathlib import Path

NANOBOT_ROOT = None
for candidate in sys.path:
    p = Path(candidate) / "nanobot"
    if (p / "agent" / "tools" / "cron.py").is_file():
        NANOBOT_ROOT = p
        break

if NANOBOT_ROOT is None:
    print("[cron_args] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)


def patch(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            print(
                f"[cron_args] ERROR: expected 1 match in {path.name}, found {count}:\n{old}",
                file=sys.stderr,
            )
            sys.exit(1)
        text = text.replace(old, new)
    path.write_text(text)
    print(f"[cron_args] patched {path.relative_to(NANOBOT_ROOT.parent)}")


NORMALIZE = '''    _ADD_TEXT_ALIASES = (
        "text", "content", "reminder", "prompt", "task", "instruction",
        "instructions", "description", "body", "note",
    )

    def cast_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().cast_params(params)
        if not isinstance(params, dict) or params.get("action") != "add":
            return params
        params = dict(params)
        message = str(params.get("message") or "").strip()
        if not message:
            for key in self._ADD_TEXT_ALIASES:
                value = params.get(key)
                if isinstance(value, str) and value.strip():
                    message = value.strip()
                    break
        job_id = params.pop("job_id", None)
        if not str(params.get("name") or "").strip() and isinstance(job_id, str) and job_id.strip():
            params["name"] = job_id.strip()
        if not message:
            name = str(params.get("name") or "").strip()
            # A label like "candele-storm-2026-11-17" is not a reminder text;
            # only use name when it reads like a sentence.
            if name and " " in name:
                message = name
        if message:
            params["message"] = message
        else:
            params.pop("message", None)
        allowed = {"action", "name", "message", "every_seconds", "cron_expr", "tz", "at"}
        return {k: v for k, v in params.items() if k in allowed}

    def validate_params(self, params: dict[str, Any]) -> list[str]:
'''

ERROR_OLD = '''        if not message:
            return ToolResult.error(
                "Error: cron action='add' requires a non-empty 'message' parameter "
                "describing what to do when the job triggers "
                "(e.g. the reminder text). Retry including message=\\"...\\"."
            )
'''

ERROR_NEW = '''        if not message:
            import json as _json
            example = {"action": "add", "message": "<reminder text for the user>"}
            if name:
                example["name"] = name
            for key, value in (("at", at), ("cron_expr", cron_expr), ("every_seconds", every_seconds), ("tz", tz)):
                if value:
                    example[key] = value
            if not (at or cron_expr or every_seconds):
                example["at"] = "<ISO datetime, e.g. 2026-11-17T07:45:00>"
            return ToolResult.error(
                "Error: cron action='add' needs the reminder text in the 'message' "
                "argument, and it was missing. Send exactly this call, with the "
                "placeholder replaced by the text to deliver: cron("
                + _json.dumps(example, ensure_ascii=False)
                + "). Do not send job_id or limit with add."
            )
'''

patch(
    NANOBOT_ROOT / "agent" / "tools" / "cron.py",
    [
        (
            "    def validate_params(self, params: dict[str, Any]) -> list[str]:\n",
            NORMALIZE,
        ),
        # Let a missing message reach _add_job, whose error shows the exact call.
        (
            "        if action == \"add\" and not str(params.get(\"message\") or \"\").strip():\n"
            "            errors.append(\"message is required when action='add'\")\n",
            "",
        ),
        (ERROR_OLD, ERROR_NEW),
        (
            '            "Updates retain the existing cron timezone when tz is omitted."\n',
            '            "Updates retain the existing cron timezone when tz is omitted. "\n'
            '            "To create a reminder send action, message (the text to deliver) and one schedule, e.g. "\n'
            '            "{\\"action\\": \\"add\\", \\"message\\": \\"Take the candles out of the car\\", "\n'
            '            "\\"at\\": \\"2026-11-17T07:45:00\\"}. job_id and limit are not used by add."\n',
        ),
    ],
)
