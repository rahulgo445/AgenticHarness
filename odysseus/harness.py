"""The Harness: the whole week composed into one object.

``Harness`` wires the provider, the loop, the tool jail, the deny policy,
context compaction, durable memory, skills, and sub-agents behind a single
``run(task)`` call. It also owns the session file: every message is written as
it lands, and ``resume`` reloads the newest session -- repaired -- so a run
survives ``kill -9`` and continues where it stopped.
"""

import os

from . import context, loop, memory, provider, session, skills
from .security import Policy
from .subagent import subagent_tool
from .tools import core_tools, tool


class Harness:
    """A configured agent over one working directory."""

    def __init__(self, workdir=".", model=None, policy=None, extra_tools=None,
                 system_extra="", on_event=None, budget_tokens=600_000,
                 max_turns=120, session_path=None, enable_subagents=True,
                 persist=True, _depth=0):
        self.workdir = os.path.realpath(workdir)
        os.makedirs(self.workdir, exist_ok=True)
        self.model = (model or os.environ.get("ODYSSEUS_MODEL")
                      or provider.DEFAULT_MODEL)
        self.policy = policy or Policy("yolo")
        self.budget_tokens = budget_tokens
        self.max_turns = max_turns
        self.persist = persist
        self.session_path = session_path
        self._depth = _depth
        self._on_event = on_event
        self.messages = []
        self._recorded = 0  # messages already written to the session file

        self.tools = {t.name: t for t in core_tools(self.workdir)}

        @tool("Save a durable one-line note to project memory (ODYSSEUS.md).",
              note="The fact to remember")
        def remember(note):
            return memory.remember(self.workdir, note)
        self.tools["remember"] = remember

        if skills.catalog(self.workdir):
            @tool("Load a skill's full instructions by name.",
                  name="Skill name from the skills-available list")
            def use_skill(name):
                return skills.read_skill(self.workdir, name)
            self.tools["use_skill"] = use_skill

        if enable_subagents:
            def make_child(child_depth):
                # persist=False: a child must never leave a session file that a
                # later --resume could pick up instead of the parent's.
                return Harness(workdir=self.workdir, model=self.model,
                               policy=self.policy, persist=False,
                               _depth=child_depth)
            self.tools["spawn_agent"] = subagent_tool(make_child, depth=_depth)

        for extra in extra_tools or []:
            self.tools[extra.name] = extra

        blocks = [skills.catalog_prompt(self.workdir), system_extra]
        self.system = memory.build_system_prompt(
            self.workdir, "\n\n".join(b for b in blocks if b))

    def resume(self, path=None):
        """Load a prior session (newest when ``path`` omitted), repaired, and
        keep writing to it. Returns True when messages were loaded."""
        path = path or session.latest(self.workdir)
        if not path:
            return False
        self.messages = session.load(path)
        self.session_path = path
        # Rewrite from the repaired list: the torn line is gone and the
        # interruption notices are baked in, so the log stays valid hereafter.
        open(path, "w", encoding="utf-8").close()
        self._recorded = 0
        self._flush()
        return bool(self.messages)

    def run(self, task):
        """Run one task to completion and return the model's final text."""
        if self.persist and self.session_path is None:
            self.session_path = session.new_session(self.workdir, task[:32])
        self.messages.append({"role": "user", "text": task})
        self._flush()

        def before_turn(messages):
            context.compact(self.model, messages, self.budget_tokens)
            self._flush()

        def on_event(kind, payload):
            self._flush()  # persist each message the instant it lands
            if self._on_event:
                self._on_event(kind, payload)

        final = loop.run_loop(self.model, self.system, self.messages,
                              self.tools, on_event, self.policy.check,
                              max_turns=self.max_turns, before_turn=before_turn)
        self._flush()
        return final

    def _flush(self):
        """Append messages not yet on disk. Clamp the index first so a
        compaction that shrank the list cannot make us skip what follows it."""
        if not self.session_path:
            return
        self._recorded = min(self._recorded, len(self.messages))
        for message in self.messages[self._recorded:]:
            session.append(self.session_path, message)
        self._recorded = len(self.messages)
