"""The permission layer: what the model is allowed to do.

``Policy.check`` is the callback ``run_loop`` consults before every tool call.
It returns ``None`` to allow or a reason string to block; the loop turns a
block into the tool result ``"BLOCKED: <reason>"`` so the model sees why and
can change course.

Design rules embodied here:
- Some shell commands are refused in every mode. ``DENY_PATTERNS`` names the
  irreversible ones: wiping ``/`` or ``$HOME``, ``sudo``, ``mkfs``/``dd``,
  piping the network into a shell, a force-push, writing over a raw disk.
- Read-only tools are always safe. Reading, listing, and grepping change
  nothing, so they pass regardless of mode.
- Everything else is a question for the human. ``safe`` mode routes it to the
  ``approver`` callback and treats anything but an explicit yes as no.
"""

import re

READ_TOOLS = {"read_file", "list_files", "grep"}

DENY_PATTERNS = [
    r"rm\s+-[-\w]*[rf][-\w]*\s+[^|;&]*(?:/|~|\$HOME)",  # rm -rf  /  ~  $HOME
    r"(?:^|[\s;&|])sudo\b",
    r"\bmkfs(?:\.\w+)?\b",
    r"\bdd\s+if=",
    r"\bcurl\b[^|]*\|\s*(?:sudo\s+)?sh\b",           # curl ... | sh
    r"\bgit\s+push\b[^;&|]*--force",
    r">\s*/dev/sd[a-z]",                              # redirect onto a raw disk
]


class Policy:
    """Decide, per tool call, whether it may run."""

    def __init__(self, mode="safe", approver=None):
        """``mode`` is 'read-only', 'safe', or 'yolo'. ``approver(call, reason)``
        returns True to permit a call in safe mode; the default refuses."""
        if mode not in ("read-only", "safe", "yolo"):
            raise ValueError("mode must be 'read-only', 'safe', or 'yolo'")
        self.mode = mode
        self.approver = approver or (lambda call, reason: False)

    def check(self, call):
        """Return None to allow the call, or a string explaining the block."""
        name = call["name"]
        if name == "bash":
            command = (call.get("args") or {}).get("command", "")
            for pattern in DENY_PATTERNS:
                if re.search(pattern, command):
                    return ("refusing an irreversible command (matched %r)"
                            % pattern)
        # Reads never mutate state; yolo opts out of every remaining check.
        if name in READ_TOOLS or self.mode == "yolo":
            return None
        if self.mode == "read-only":
            return "read-only mode: %s can modify state" % name
        reason = "safe mode: %s needs your approval" % name
        return None if self.approver(call, reason) else reason
