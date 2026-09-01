"""A long task under a tiny context budget: compaction keeps the loop alive.

``before_turn`` runs ``compact`` before every model call. When the transcript
outgrows ``BUDGET`` tokens it collapses to a dense recap plus the last few
messages, and the run carries on. Run from the repo root::

    python demos/context_compaction.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import provider
from odysseus.context import compact, estimate_tokens
from odysseus.loop import run_loop
from odysseus.memory import build_system_prompt
from odysseus.security import Policy
from odysseus.tools import core_tools

BUDGET = 1500


def main():
    """Run a multi-file task with the context budget deliberately set too low."""
    workdir = tempfile.mkdtemp(prefix="odysseus-compact-")
    tools = {t.name: t for t in core_tools(workdir)}

    def before_turn(messages):
        """Compact in place, and print a line whenever the transcript shrinks."""
        before = len(messages)
        compact(provider.DEFAULT_MODEL, messages, BUDGET)
        if len(messages) < before:
            print("[compact] %d -> %d messages (~%d tokens kept)"
                  % (before, len(messages), estimate_tokens(messages)))

    def on_event(kind, payload):
        if kind == "assistant":
            for call in payload["tool_calls"]:
                print("[assistant] -> %s(%s)" % (call["name"], call["args"]))
            if payload["text"].strip():
                print("[assistant] %s" % payload["text"].strip()[:300])
        elif kind == "tool_end":
            first = str(payload["result"]).splitlines()[:1]
            print("[tool_end]   %s" % (first[0][:120] if first else ""))

    task = ("Create five files one.txt through five.txt, each with 20 lines of "
            "the word ping, one write_file at a time with a read back after "
            "each; then MANIFEST.md listing each file and its line count "
            "verified with wc -l.")
    messages = [{"role": "user", "text": task}]
    answer = run_loop(provider.DEFAULT_MODEL, build_system_prompt(workdir),
                      messages, tools, on_event, Policy("yolo").check,
                      before_turn=before_turn)
    print("\nFINAL: %s" % answer)
    print("(workdir: %s)" % workdir)


if __name__ == "__main__":
    main()
