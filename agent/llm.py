"""Single entry point for LLM calls, via Meterless/Nightshift.

Usage:
    from agent.llm import ask, LLMError
    answer = ask([{"role": "user", "content": "..."}])
    answer = ask(messages, model="nvidia/nemotron-3-super-120b-a12b")  # override
"""
import os

import openai
from dotenv import load_dotenv
from openai import OpenAI

# ── Section A: config ─────────────────────────────
load_dotenv()

BASE_URL = os.environ.get("METERLESS_BASE_URL")
TOKEN = os.environ.get("METERLESS_RUNTIME_TOKEN")
DEFAULT_MODEL = os.environ.get("METERLESS_MODEL", "meterless/auto")
APP_NAME = "mc-crash-investigator"

if not BASE_URL:
    raise RuntimeError(
        "METERLESS_BASE_URL not set. Is .env in the project root?"
    )
if not TOKEN:
    raise RuntimeError(
        "METERLESS_RUNTIME_TOKEN not set. Is .env in the project root? "
        "(Use the Nightshift Console token, not the NVIDIA key.)"
    )

# ── Section B: one shared client ──────────────────
client = OpenAI(
    base_url=BASE_URL,
    api_key=TOKEN,  # sent as "Authorization: Bearer <token>"
    default_headers={
        "meterless-app": APP_NAME,
        "meterless-scope": "user",
    },
    timeout=60,
)


# ── Section C: our own error type ─────────────────
class LLMError(Exception):
    """Raised when an LLM call fails, with a hint about why."""


# ── Section D: the function everyone calls ────────
def ask(messages, model=None) -> str:
    """Send a chat request and return the reply text.

    messages: list of {"role": ..., "content": ...} dicts
    model:    optional override; defaults to METERLESS_MODEL from .env
    Raises LLMError on any failure, including an empty reply.
    """
    chosen = model or DEFAULT_MODEL

    try:
        resp = client.chat.completions.create(model=chosen, messages=messages)
    # Order matters: AuthenticationError is a subclass of APIStatusError.
    except openai.APIConnectionError as e:
        raise LLMError(
            f"Can't reach Nightshift at {BASE_URL}. "
            "Is Nightshift running, and is the URL/port right?"
        ) from e
    except openai.AuthenticationError as e:
        raise LLMError(
            "Token rejected by Nightshift (401). METERLESS_RUNTIME_TOKEN must be "
            "the Console token, not the NVIDIA key."
        ) from e
    except openai.APIStatusError as e:
        raise LLMError(
            f"Nightshift returned HTTP {e.status_code} for model '{chosen}': "
            f"{e.message}"
        ) from e

    # A non-Nightshift server (e.g. a web page on the wrong port) can answer
    # with HTML/plain text; the SDK then hands back a str, not a completion.
    if not hasattr(resp, "choices"):
        snippet = str(resp)[:200].replace("\n", " ")
        raise LLMError(
            f"Got a non-API response from {BASE_URL}. Something answered, but "
            f"it isn't Nightshift's OpenAI endpoint. Check the port/path. "
            f"Response started with: {snippet!r}"
        )

    if not resp.choices:
        raise LLMError(f"No choices returned for model '{chosen}'.")

    content = resp.choices[0].message.content
    if not content or not content.strip():
        raise LLMError(
            f"Empty reply from model '{chosen}' (possible NVIDIA zero-tokens "
            "issue, or no active lane)."
        )

    return content.strip()