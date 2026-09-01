"""Skills: folders of instructions the agent can pull in on demand.

A skill is a directory ``skills/<name>/`` holding a ``SKILL.md``. ``catalog``
finds them (re-reading disk each call, so dropping a folder in is enough),
``catalog_prompt`` advertises just their one-line descriptions in the system
prompt, and ``read_skill`` returns the full text only once the agent asks --
the instructions cost context, so they arrive only when a skill applies.
"""

import os

SKILLS_DIR = "skills"


def catalog(workdir):
    """Map skill name -> {"description", "path"} for each skills/<name>/SKILL.md."""
    base = os.path.join(os.path.realpath(workdir), SKILLS_DIR)
    found = {}
    if not os.path.isdir(base):
        return found
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name, "SKILL.md")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as handle:
                found[name] = {"description": _description(handle.read()),
                               "path": path}
    return found


def catalog_prompt(workdir):
    """A system-prompt block listing the available skills, or "" when there are none."""
    found = catalog(workdir)
    if not found:
        return ""
    lines = ["Skills available (load one with the use_skill tool when relevant):"]
    lines += ["- %s: %s" % (name, meta["description"])
              for name, meta in found.items()]
    return "\n".join(lines)


def read_skill(workdir, name):
    """Return the named skill's full SKILL.md text, or an ERROR string on a miss."""
    found = catalog(workdir)
    if name not in found:
        return ("ERROR: no skill named %s. Available: %s"
                % (name, ", ".join(found) or "(none)"))
    with open(found[name]["path"], "r", encoding="utf-8") as handle:
        return handle.read()


def _description(text):
    """The value of the first front-matter ``description:`` line, or ""."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("description:"):
            return stripped.split(":", 1)[1].strip()
    return ""
