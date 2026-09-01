"""Skills: a folder of instructions that reshapes behavior with no code change.

A ``brand-voice`` skill is advertised in the system prompt; the agent loads it
with ``use_skill`` and the writing task comes back in that voice. Nothing in
the harness changed. Run from the repo root::

    python demos/skill_voice.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import provider
from odysseus.loop import run_loop
from odysseus.memory import build_system_prompt
from odysseus.skills import catalog_prompt, read_skill
from odysseus.tools import core_tools, tool

SKILL_MD = """---
description: Required brand voice for all user-facing copy -- write like a pirate.
---
# Brand voice

Every user-facing sentence must sound like a cheerful pirate: "Ahoy", "matey",
"ye", "yer", "aye", nautical metaphors. Keep the meaning exact; change only
the voice.
"""


def main():
    """Plant a brand-voice skill, then run a plain writing task through the loop."""
    workdir = tempfile.mkdtemp(prefix="odysseus-skill-")
    skill_dir = os.path.join(workdir, "skills", "brand-voice")
    os.makedirs(skill_dir)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(SKILL_MD)

    @tool("Load a skill's full instructions by name.",
          name="Skill name from the skills-available list")
    def use_skill(name):
        return read_skill(workdir, name)

    tools = {t.name: t for t in core_tools(workdir)}
    tools[use_skill.name] = use_skill

    def on_event(kind, payload):
        if kind == "assistant":
            for call in payload["tool_calls"]:
                print("[assistant] -> %s(%s)" % (call["name"], call["args"]))
            if payload["text"].strip():
                print("[assistant] %s" % payload["text"].strip())

    system = build_system_prompt(workdir, extra=catalog_prompt(workdir))
    messages = [{"role": "user", "text":
                 "Write a two-sentence welcome blurb for our app's home page."}]
    answer = run_loop(provider.DEFAULT_MODEL, system, messages, tools,
                      on_event, lambda call: None)
    print("\nFINAL: %s" % answer)


if __name__ == "__main__":
    main()
