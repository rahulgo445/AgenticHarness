"""Fleet: three small builds at once, one working directory each.

``run_fleet`` fans the jobs across a thread pool; each gets its own Harness
jailed to its own directory, and the reports come back in input order. Run
from the repo root::

    python demos/fleet_build.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import Harness, run_fleet


def make_harness(workdir):
    """One agent per job, confined to its own directory."""
    return Harness(workdir=workdir, max_turns=60)


def main():
    root = tempfile.mkdtemp(prefix="odysseus-fleet-")
    jobs = [
        {"name": "fizzbuzz", "workdir": os.path.join(root, "fizzbuzz"),
         "task": "Write fizzbuzz.py printing 1..30, then run it and confirm."},
        {"name": "palindrome", "workdir": os.path.join(root, "palindrome"),
         "task": "Write palindrome.py with is_palindrome(s) and a __main__ of "
                 "5 asserts; run it green."},
        {"name": "wordcount", "workdir": os.path.join(root, "wordcount"),
         "task": "Write wc.py that counts words on stdin; prove it with a "
                 "bash echo pipe."},
    ]
    for result in run_fleet(jobs, make_harness, max_workers=3):
        mark = "ok " if result["ok"] else "FAIL"
        print("[%s] %s  %s" % (mark, result["name"],
                               result["report"].splitlines()[0][:100]))
    print("\nworkdirs under: %s" % root)


if __name__ == "__main__":
    main()
