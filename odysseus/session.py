"""Durable sessions: the transcript survives a crash.

Every message the loop produces is appended to a JSONL file as it lands, so a
killed process loses only whatever was halfway through being written. ``load``
tolerates that torn final line, then repairs the call/response pairing: any
tool call the crash left unanswered is given a synthetic interruption notice,
so the restored transcript is valid input for the provider again.
"""

import json
import os
import re
import time

SESSION_DIR = ".odysseus/sessions"
INTERRUPTED = "Interrupted before this ran (process restarted)."


def new_session(workdir, label="session"):
    """Create the session directory and return a fresh ``<ts>-<slug>.jsonl`` path."""
    directory = os.path.join(os.path.realpath(workdir), SESSION_DIR)
    os.makedirs(directory, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:40].strip("-")
    return os.path.join(directory,
                        "%d-%s.jsonl" % (time.time(), slug or "session"))


def append(path, message):
    """Append one message to the session file as a JSON line (UTF-8, unescaped)."""
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(message, ensure_ascii=False) + "\n")


def load(path):
    """Parse the session file line by line, stop at the first torn line, then
    repair any dangling tool call and return the message list."""
    messages = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except ValueError:
                break  # a crash mid-write left this line half-formed
    _repair(messages)
    return messages


def latest(workdir):
    """The most recently modified ``.jsonl`` in the session dir, or None."""
    directory = os.path.join(os.path.realpath(workdir), SESSION_DIR)
    if not os.path.isdir(directory):
        return None
    files = [os.path.join(directory, name) for name in os.listdir(directory)
             if name.endswith(".jsonl")]
    return max(files, key=os.path.getmtime) if files else None


def _repair(messages):
    """Answer every tool call a crash left dangling, so the provider's
    one-response-per-call rule holds again."""
    last = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            last = i
            break
    if last is None:
        return
    calls = messages[last].get("tool_calls") or []
    answered = sum(1 for m in messages[last + 1:] if m.get("role") == "tool")
    for call in calls[answered:]:
        messages.append({"role": "tool", "name": call.get("name"),
                         "text": INTERRUPTED})
