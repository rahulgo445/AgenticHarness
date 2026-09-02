"""The ``odysseus`` command line -- the harness's front door.

Two shapes. ``odysseus -p "task"`` runs one task headless and exits; bare
``odysseus`` opens an interactive prompt loop. Both stream the agent's work
as it happens and, in safe mode, stop to ask before any state-changing tool.
"""

import argparse
import sys

from .harness import Harness
from .security import Policy

_TTY = sys.stdout.isatty()
_DIM, _OFF = ("\033[2m", "\033[0m") if _TTY else ("", "")


def _clip(args, limit=140):
    """One-line ``k=repr(v)`` rendering of a tool call's arguments, clipped."""
    text = ", ".join("%s=%r" % kv for kv in (args or {}).items())
    return text if len(text) <= limit else text[:limit] + "..."


def _printer(kind, payload):
    """Event sink: assistant prose plain, each tool call a line with its
    first result line dimmed beneath it."""
    if kind == "assistant":
        if payload["text"].strip():
            print(payload["text"].strip())
    elif kind == "tool_start":
        print("-> %s(%s)" % (payload["name"], _clip(payload["args"])))
    elif kind == "tool_end":
        head = str(payload["result"]).splitlines()[:1]
        print("%s   %s%s" % (_DIM, head[0][:200] if head else "", _OFF))


def _approver(call, reason):
    """Show the pending call and ask for a yes; anything else is a no."""
    print("\n%s wants: %s(%s)\n  reason: %s"
          % ("odysseus", call["name"], _clip(call.get("args")), reason))
    try:
        return input("approve %s? [y/N] " % call["name"]).strip().lower() in (
            "y", "yes")
    except EOFError:
        return False


def _interactive(harness, mode):
    """Banner, then a prompt loop: Ctrl-D quits, Ctrl-C aborts the current run."""
    print("odysseus  |  model %s  |  mode %s  |  jail %s"
          % (harness.model, mode, harness.workdir))
    print("Ctrl-D to exit, Ctrl-C to interrupt a run.")
    while True:
        try:
            task = input("\nodysseus> ").strip()
        except EOFError:
            print()
            return
        except KeyboardInterrupt:
            print()
            continue
        if not task:
            continue
        try:
            harness.run(task)
        except KeyboardInterrupt:
            print("\n[interrupted] the session log is safe -- "
                  "rerun with --resume to continue it.")


def main(argv=None):
    """Parse arguments and dispatch to the headless or interactive path."""
    parser = argparse.ArgumentParser(
        prog="odysseus", description="A small, sharp coding agent.")
    parser.add_argument("-p", "--prompt", help="run this task headless, then exit")
    parser.add_argument("-d", "--workdir", default=".",
                        help="directory the agent is jailed to (default: .)")
    parser.add_argument("-m", "--model", help="override the model")
    parser.add_argument("--mode", choices=("safe", "yolo", "read-only"),
                        help="permission mode (default: safe, or yolo with -p)")
    parser.add_argument("--resume", action="store_true",
                        help="continue the newest session in the workdir")
    parser.add_argument("--max-turns", type=int, default=120)
    args = parser.parse_args(argv)

    mode = args.mode or ("yolo" if args.prompt else "safe")
    policy = Policy(mode, approver=_approver if mode == "safe" else None)
    harness = Harness(workdir=args.workdir, model=args.model, policy=policy,
                      on_event=_printer, max_turns=args.max_turns)

    if args.resume:
        loaded = harness.resume()
        print("[resume] %s"
              % ("%d messages" % len(harness.messages) if loaded
                 else "nothing to resume"))

    if args.prompt:
        harness.run(args.prompt)
        return 0
    _interactive(harness, mode)
    return 0
