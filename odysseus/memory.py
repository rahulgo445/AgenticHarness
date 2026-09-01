"""Durable memory: the system prompt the agent wakes up with.

``build_system_prompt`` assembles what every run of Odysseus is told before it
sees the task: the standing rules, the environment it is in, and -- when the
working directory carries an ``ODYSSEUS.md`` -- whatever past runs chose to
write down. ``remember`` is how a run adds to that file.

Design rules embodied here:
- Memory is a plain file in the project, not a hidden store. A human can read
  and edit ``ODYSSEUS.md``; the agent only ever appends bullet lines to it.
- The prompt is built fresh each run from the file on disk, so a fact written
  in one conversation is present, unprompted, in the next.
"""

import os
import platform

MEMORY_FILE = "ODYSSEUS.md"

BASE_PROMPT = (
    "You are Odysseus, a small, sharp coding agent. You work inside a single "
    "directory using only the tools provided.\n"
    "- Act, don't narrate: make the change instead of describing it.\n"
    "- Inspect before assuming: read files and run checks rather than guessing.\n"
    "- Prefer edit_file for small changes; use write_file for new files or a "
    "full rewrite.\n"
    "- After building, verify by running the code or re-reading what you wrote.\n"
    "- Never repeat a failing call unchanged -- change the input or the "
    "approach.\n"
    "- When the task is done, reply with a short summary and stop calling tools."
)


def build_system_prompt(workdir, extra=""):
    """Return the base prompt, an environment line, the project's ODYSSEUS.md
    (when present), and ``extra`` (when non-empty), separated by blank lines."""
    root = os.path.realpath(workdir)
    parts = [BASE_PROMPT,
             "Platform: %s\nWorking directory: %s" % (platform.platform(), root)]
    memo = os.path.join(root, MEMORY_FILE)
    if os.path.exists(memo):
        with open(memo, "r", encoding="utf-8") as handle:
            parts.append("Project memory (%s):\n%s" % (MEMORY_FILE, handle.read()))
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


def remember(workdir, note):
    """Append ``note`` as a bullet line to the project's ODYSSEUS.md."""
    path = os.path.join(os.path.realpath(workdir), MEMORY_FILE)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("- %s\n" % note)
    return "Remembered in %s" % MEMORY_FILE
