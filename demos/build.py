"""A coding agent: core tools, a permissive policy, one build task.

Wires ``core_tools`` over a throwaway scratch directory into ``run_loop`` with
``Policy("yolo").check`` as the gate -- so every ordinary call runs while the
deny list still stops the irreversible ones. Run from the repo root::

    python demos/build.py

The transcript shows the model writing a file, running it, reading the output,
and only then answering.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import provider
from odysseus.loop import run_loop
from odysseus.security import Policy
from odysseus.tools import core_tools


def on_event(kind, payload):
    """Print a one-line trace for each loop event, clipping long tool output."""
    if kind == "assistant":
        for call in payload["tool_calls"]:
            print("[assistant] -> %s(%s)" % (call["name"], call["args"]))
        text = payload["text"].strip()
        if text:
            print("[assistant] %s" % text)
    elif kind == "tool_start":
        print("[tool_start] %s" % payload["name"])
    elif kind == "tool_end":
        result = str(payload["result"])
        if len(result) > 500:
            result = result[:500] + " ..."
        print("[tool_end]   %s" % result.replace("\n", "\n             "))


def main():
    """Run the build task in a fresh scratch directory and print the answer."""
    workdir = tempfile.mkdtemp(prefix="odysseus-build-")
    tools = {t.name: t for t in core_tools(workdir)}
    policy = Policy("yolo")
    task = ("Create fib.py with an iterative fib(n), a __main__ that prints "
            "fib(30), run it, and confirm the output is 832040.")
    messages = [{"role": "user", "text": task}]
    answer = run_loop(
        provider.DEFAULT_MODEL,
        "You are a coding agent working in %s. Use the tools to make the change "
        "and verify it by running code before you answer." % workdir,
        messages, tools, on_event, policy.check,
    )
    print("\nFINAL: %s" % answer)
    print("(scratch dir: %s)" % workdir)


if __name__ == "__main__":
    main()
