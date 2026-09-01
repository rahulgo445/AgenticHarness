"""Odysseus: a small, sharp coding-agent harness.

The public surface is ``Harness`` -- compose and run an agent over a
directory -- plus ``Policy``, ``Tool``, and the ``tool`` decorator for
configuring one.
"""

from .harness import Harness
from .security import Policy
from .tools import Tool, tool

__all__ = ["Harness", "Policy", "Tool", "tool"]
