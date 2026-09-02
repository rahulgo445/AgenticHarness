"""Fleet: run many harnesses at once.

``run_fleet`` fans a list of jobs across a thread pool -- each in its own
working directory with its own Harness -- and returns the results in the order
the jobs were given. One job raising becomes a failed entry, never a crash of
the whole run.
"""

from concurrent.futures import ThreadPoolExecutor


def run_fleet(jobs, make_harness, max_workers=4):
    """Run each job's task concurrently and collect ordered results.

    ``jobs`` is a list of ``{"name", "workdir", "task"}``. Each job runs
    ``make_harness(workdir).run(task)``. Returns one dict per job, in input
    order: ``{"name", "ok": True, "report": <final text>}`` on success, or
    ``{"name", "ok": False, "report": "<ExceptionType>: <message>"}`` when the
    run raised.
    """
    def one(job):
        try:
            report = make_harness(job["workdir"]).run(job["task"])
            return {"name": job["name"], "ok": True, "report": report}
        except Exception as exc:  # a job failure is a result, not a crash
            return {"name": job["name"], "ok": False,
                    "report": "%s: %s" % (type(exc).__name__, exc)}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(one, jobs))  # pool.map preserves input order
