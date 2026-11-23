"""Keeping chat replies short, by code: the prompts ask the agents for two short sentences, and these
helpers hold the line when a model writes more. Details belong in the artifacts, not in the chat."""

import re

REPLY_LIMIT = 320  # characters of model prose shown in a chat reply, about two sentences
LIST_LIMIT = 5  # lines of a computed list (drift, problems) shown in a chat reply

_SENTENCE_END = re.compile(r"[.!?](?=\s|$)")


def brief(text: str, limit: int = REPLY_LIMIT) -> str:
    """The text on one line, cut at the last sentence end within `limit` characters. A soft cap: a
    long text is shortened, never refused, so no model call is repeated because of length."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    ends = [m.end() for m in _SENTENCE_END.finditer(flat) if m.end() <= limit]
    if ends:
        return flat[: ends[-1]]
    return flat[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " ..."


def short_list(lines: list[str], where: str, limit: int = LIST_LIMIT) -> list[str]:
    """The first lines of a computed list and a count of the rest, with the place that has them all."""
    if len(lines) <= limit:
        return list(lines)
    return [*lines[:limit], f"and {len(lines) - limit} more ({where})"]
