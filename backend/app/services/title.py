"""Generates a short session title from the user's first message, locally —
no Gemini call, to keep session creation free and fast."""
import re

_MAX_TITLE_WORDS = 8
_MAX_TITLE_CHARS = 60


def generate_title(first_message: str) -> str:
    text = re.sub(r"\s+", " ", first_message).strip()
    if not text:
        return "New bug"

    first_sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
    words = first_sentence.split(" ")[:_MAX_TITLE_WORDS]
    title = " ".join(words)

    if len(title) > _MAX_TITLE_CHARS:
        title = title[:_MAX_TITLE_CHARS].rsplit(" ", 1)[0]

    if len(words) < len(first_sentence.split(" ")) or len(title) < len(first_sentence):
        title += "…"

    return title[0].upper() + title[1:] if title else "New bug"
