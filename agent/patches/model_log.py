"""Patch nanobot so every LLM reply logs which model actually served it.

With ``openrouter/auto`` the gateway only logs ``model=openrouter/auto``, so a
broken tool call (e.g. cron add without its message, 19 Nov 2026) cannot be
traced back to the routed model that made it. OpenRouter returns the real model
in the ``model`` field of each response / stream chunk.

After this patch the OpenAI-compatible provider logs one line per LLM reply:

    LLM reply served by model=<routed model> tool_calls=[cron, ...]

so offending models can be put on the Auto Router's excluded list.

Run once after ``pip install nanobot-ai``. Fails loudly if the upstream code
changed, so a nanobot bump cannot silently ship without the patch.
"""

import sys
from pathlib import Path

NANOBOT_ROOT = None
for candidate in sys.path:
    p = Path(candidate) / "nanobot"
    if (p / "providers" / "openai_compat_provider.py").is_file():
        NANOBOT_ROOT = p
        break

if NANOBOT_ROOT is None:
    print("[model_log] ERROR: could not locate nanobot package", file=sys.stderr)
    sys.exit(1)


def patch(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text()
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            print(
                f"[model_log] ERROR: expected 1 match in {path.name}, found {count}:\n{old}",
                file=sys.stderr,
            )
            sys.exit(1)
        text = text.replace(old, new)
    path.write_text(text)
    print(f"[model_log] patched {path.relative_to(NANOBOT_ROOT.parent)}")


HELPER = '''

def _served_model_of(obj: Any) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        value = obj.get("model")
    else:
        value = getattr(obj, "model", None)
    return value if isinstance(value, str) and value else None


def _log_served_model(model: str | None, tool_calls: list[Any]) -> None:
    try:
        names = [getattr(tc, "name", "?") for tc in tool_calls or []]
        logger.info("LLM reply served by model={} tool_calls={}", model or "?", names)
    except Exception:
        pass
'''

patch(
    NANOBOT_ROOT / "providers" / "openai_compat_provider.py",
    [
        (
            "from loguru import logger\n",
            "from loguru import logger\n",
        ),
        # _parse (non-streaming)
        (
            "        return LLMResponse(\n"
            "            content=content,\n"
            "            tool_calls=parsed_tool_calls,\n",
            "        _log_served_model(_served_model_of(response_map), parsed_tool_calls)\n"
            "        return LLMResponse(\n"
            "            content=content,\n"
            "            tool_calls=parsed_tool_calls,\n",
        ),
        # _parse_chunks (streaming)
        (
            "        return LLMResponse(\n"
            "            content=content,\n"
            "            tool_calls=tool_calls,\n"
            "            finish_reason=finish_reason,\n"
            "            usage=usage,\n",
            "        _log_served_model(\n"
            "            next((m for m in (_served_model_of(c) for c in chunks) if m), None),\n"
            "            tool_calls,\n"
            "        )\n"
            "        return LLMResponse(\n"
            "            content=content,\n"
            "            tool_calls=tool_calls,\n"
            "            finish_reason=finish_reason,\n"
            "            usage=usage,\n",
        ),
    ],
)

# Module-level helpers go at the end of the file (names resolve at call time).
_path = NANOBOT_ROOT / "providers" / "openai_compat_provider.py"
_path.write_text(_path.read_text() + HELPER)
