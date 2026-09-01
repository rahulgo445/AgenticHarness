"""Delegation: the parent farms out subtasks, then verifies the result itself.

The parent uses ``spawn_agent`` twice -- one child writes ``utils.py``, another
writes ``test_utils.py`` -- then runs the tests itself. Children are built
``persist=False``, so only the parent leaves a session file. Run from the repo
root::

    python demos/subagent_delegation.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import Harness

TASK = ("Use spawn_agent twice: delegate writing utils.py with a slugify(text) "
        "function to one child, and test_utils.py with five asserts covering "
        "slugify to another; then run python3 test_utils.py yourself and report "
        "the result.")


def on_event(kind, payload):
    """Trace the parent's turns; long tool args are clipped."""
    if kind == "assistant":
        for call in payload["tool_calls"]:
            shown = str(call["args"])
            if len(shown) > 160:
                shown = shown[:160] + " ..."
            print("[assistant] -> %s(%s)" % (call["name"], shown))
        if payload["text"].strip():
            print("[assistant] %s" % payload["text"].strip())
    elif kind == "tool_end":
        print("[tool_end]   %s" % str(payload["result"]).splitlines()[0][:100])


def main():
    workdir = tempfile.mkdtemp(prefix="odysseus-subagents-")
    harness = Harness(workdir=workdir, on_event=on_event)
    answer = harness.run(TASK)
    print("\nFINAL: %s" % answer)

    sessions = os.listdir(os.path.join(harness.workdir, ".odysseus", "sessions"))
    print("session files: %s  (expect exactly 1)" % sessions)
    print("workdir files: %s" % sorted(f for f in os.listdir(harness.workdir)
                                       if not f.startswith(".")))


if __name__ == "__main__":
    main()
