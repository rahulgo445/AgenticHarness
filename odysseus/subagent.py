"""Sub-agents: hand a self-contained task to a fresh context.

``spawn_agent`` lets the model delegate work that does not need the current
conversation. The child is a brand-new Harness with its own clean transcript
that cannot see this one; only its final report comes back. Recursion is
capped so nothing spawns without bound.
"""

from .tools import tool

DEPTH_LIMIT = "ERROR: sub-agent depth limit reached; do this task yourself"


def subagent_tool(make_harness, depth=0, max_depth=2):
    """Build the ``spawn_agent`` Tool. ``make_harness(child_depth)`` returns the
    child Harness; delegation is refused at or past ``max_depth``."""

    @tool("Delegate a self-contained task to a fresh sub-agent with its own "
          "clean context. The child cannot see this conversation; you get back "
          "only its final report.",
          task="A complete, standalone description of the work for the child")
    def spawn_agent(task):
        if depth >= max_depth:
            return DEPTH_LIMIT
        return make_harness(depth + 1).run(task)

    return spawn_agent
