"""Crash and resume: a killed run picks up from the session file.

Two modes over one fixed directory. ``start`` begins a multi-file task with a
deliberately slowed write_file, so the process can be killed while a tool is
in flight; ``resume`` reloads the repaired session and continues. Run from the
repo root::

    python demos/session_resume.py start /tmp/odysseus-resume-demo
    kill -9 <printed pid>          # partway through
    python demos/session_resume.py resume /tmp/odysseus-resume-demo
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import Harness
from odysseus.tools import Tool, core_tools

TASK = ("Create part1.txt through part5.txt one at a time, then SUMMARY.md "
        "describing each.")
NOTICE = "Interrupted before this ran (process restarted)."


def on_event(kind, payload):
    """Trace loop events, flushed so a kill can't strand buffered output."""
    if kind == "assistant":
        for call in payload["tool_calls"]:
            print("[assistant] -> %s(%s)" % (call["name"], call["args"]),
                  flush=True)
        if payload["text"].strip():
            print("[assistant] %s" % payload["text"].strip()[:200], flush=True)
    elif kind == "tool_end":
        head = str(payload["result"]).splitlines()[:1]
        print("[tool_end]   %s" % (head[0][:80] if head else ""), flush=True)


def slow_write(workdir):
    """write_file with a 2s pause up front, to widen the kill window."""
    base = {t.name: t for t in core_tools(workdir)}["write_file"]

    def run(**kwargs):
        time.sleep(2.0)
        return base.run(**kwargs)

    return Tool(base.name, base.spec, run)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "start"
    workdir = os.path.realpath(
        sys.argv[2] if len(sys.argv) > 2 else "/tmp/odysseus-resume-demo")
    harness = Harness(workdir=workdir, on_event=on_event,
                      extra_tools=[slow_write(workdir)])

    if mode == "start":
        print("PID %d  workdir %s" % (os.getpid(), harness.workdir), flush=True)
        print(harness.run(TASK))
    else:
        loaded = harness.resume()
        print("resumed=%s  messages=%d" % (loaded, len(harness.messages)))
        print("interruption notice in transcript: %s"
              % any(m.get("text") == NOTICE for m in harness.messages))
        print(harness.run("continue the task"))
        files = sorted(f for f in os.listdir(harness.workdir)
                       if f.endswith((".txt", ".md")))
        print("files now: %s" % files)


if __name__ == "__main__":
    main()
