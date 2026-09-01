"""Durable memory: what one run writes down, the next run knows without asking.

A fact is stored with ``remember``; then a brand-new conversation over the
same directory -- no history, no tools -- answers a question about it purely
from ``build_system_prompt``. Run from the repo root::

    python demos/memory_recall.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import provider
from odysseus.loop import run_loop
from odysseus.memory import build_system_prompt, remember


def on_event(kind, payload):
    """Print the assistant's text; this run makes no tool calls."""
    if kind == "assistant" and payload["text"].strip():
        print("[assistant] %s" % payload["text"].strip())


def main():
    """Write a fact, then recall it in a fresh conversation with no tools."""
    workdir = tempfile.mkdtemp(prefix="odysseus-memory-")
    print(remember(workdir, "The deploy target is fly.io, region ord, app name "
                            "'odysseus-demo'."))

    # Fresh conversation: no prior messages, an empty tool set. The only place
    # the fact can come from is the system prompt, which now carries ODYSSEUS.md.
    messages = [{"role": "user", "text":
                 "Which region do we deploy to, and what is the app name?"}]
    answer = run_loop(provider.DEFAULT_MODEL, build_system_prompt(workdir),
                      messages, {}, on_event, lambda call: None)
    print("\nFINAL: %s" % answer)


if __name__ == "__main__":
    main()
