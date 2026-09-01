"""One hand-written tool through the loop.

The smallest useful shape of a tool is an object with ``.spec`` (the JSON
schema the model sees) and ``.run`` (the callable the loop invokes with
keyword arguments). Nothing here is framework magic; the loop only needs
those two attributes.

Run it from the repo root::

    python demos/dice.py

The printed transcript shows four beats: the user task, the assistant's tool
call, the tool result, and the assistant's final answer.
"""

import os
import random
import sys

# A demo script is run by path, so the repo root is not yet importable; add it
# before importing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import provider
from odysseus.loop import run_loop


class RollDice:
    """Roll ``count`` six-sided dice and return the individual rolls."""

    # count is typed "string" on purpose: Gemini sends function args as JSON
    # strings, and .run below is written to accept that and convert.
    spec = {"schema": {
        "name": "roll_dice",
        "description": "Roll count six-sided dice",
        "parameters": {
            "type": "object",
            "properties": {
                "count": {"type": "string", "description": "How many dice"},
            },
            "required": ["count"],
        },
    }}

    def run(self, count):
        """Return a list of ``int(count)`` rolls, each 1-6."""
        return [random.randint(1, 6) for _ in range(int(count))]


def on_event(kind, payload):
    """Print a one-line trace for each loop event."""
    if kind == "assistant":
        for call in payload["tool_calls"]:
            print("[assistant] -> %s(%s)" % (call["name"], call["args"]))
        text = payload["text"].strip()
        if text:
            print("[assistant] %s" % text)
    elif kind == "tool_start":
        print("[tool_start] %s(%s)" % (payload["name"], payload["args"]))
    elif kind == "tool_end":
        print("[tool_end]   %s" % (payload["result"],))


def before_tool(call):
    """Allow every tool call (this demo has no policy to enforce)."""
    return None


def main():
    """Give the model the dice task and print the final answer."""
    tools = {"roll_dice": RollDice()}
    messages = [{"role": "user",
                 "text": "Roll 3 dice and tell me whether the total beats 10"}]
    answer = run_loop(
        provider.DEFAULT_MODEL,
        "You are a dice assistant. Use the roll_dice tool, then report the "
        "rolls, their total, and whether the total beats 10.",
        messages, tools, on_event, before_tool,
    )
    print("\nFINAL: %s" % answer)


if __name__ == "__main__":
    main()
