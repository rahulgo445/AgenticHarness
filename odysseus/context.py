"""The context engine: keeping the transcript inside the model's window.

``compact()`` is what the loop's ``before_turn`` seam calls before every turn.
While the message list fits the token budget it is returned untouched; once it
outgrows the budget, everything but the last ``KEEP_RECENT`` messages becomes
one dense summary and the run continues. Token counting is a deliberately
cheap estimate -- characters over ``CHARS_PER_TOKEN`` -- since it only decides
when to fold.
"""

from . import provider

CHARS_PER_TOKEN = 4
KEEP_RECENT = 6
MESSAGE_CLIP = 500  # per-message cap when flattening old turns to text

SUMMARY_SYSTEM = ("You compress agent transcripts. Preserve: the original "
                  "task, every file created or edited and its purpose, key "
                  "decisions, unresolved errors, and what remains to be done. "
                  "Be dense and factual.")


def estimate_tokens(messages):
    """Rough token count: total ``str`` length of the messages / CHARS_PER_TOKEN."""
    return sum(len(str(message)) for message in messages) // CHARS_PER_TOKEN


def compact(model, messages, budget_tokens):
    """Summarize all but the last ``KEEP_RECENT`` messages when over budget.

    Returns the (possibly unchanged) list and also rewrites ``messages`` in
    place, because the loop consumes the list by identity, not by return value.
    A dangling tool result is dropped from the kept tail so the slice opens on
    a user or assistant turn -- the provider rejects a leading functionResponse.
    """
    if (estimate_tokens(messages) <= budget_tokens
            or len(messages) <= KEEP_RECENT + 1):
        return messages
    old, recent = messages[:-KEEP_RECENT], messages[-KEEP_RECENT:]
    summary = provider.complete(
        model, SUMMARY_SYSTEM,
        [{"role": "user", "text": _render(old)}], [])["text"]
    while recent and recent[0]["role"] == "tool":
        recent = recent[1:]
    messages[:] = [{"role": "user", "text":
                    "[Conversation so far, compacted]\n%s" % summary}] + recent
    return messages


def _render(messages):
    """Flatten messages to a plain transcript: role, tool name, clipped text,
    and the names of any tool calls."""
    lines = []
    for message in messages:
        head = message["role"]
        if message.get("name"):
            head += " " + message["name"]
        text = str(message.get("text", ""))
        if len(text) > MESSAGE_CLIP:
            text = text[:MESSAGE_CLIP] + " ...[clipped]"
        if message.get("tool_calls"):
            text += " (calls: %s)" % ", ".join(
                c["name"] for c in message["tool_calls"])
        lines.append("%s: %s" % (head, text))
    return "\n".join(lines)
