# Odysseus

The smallest agent harness that still does real work: **ten files, zero
dependencies**, Python 3.10+ standard library only. It talks to one model,
runs tools in a jailed directory, keeps its own context under budget,
remembers things between runs, survives `kill -9`, and can fan out across a
fleet of working directories.

## Run it

Set a key (either name works; `ODYSSEUS_API_KEY` wins):

```bash
export ODYSSEUS_API_KEY=…      # or GEMINI_API_KEY
export ODYSSEUS_MODEL=…        # optional, overrides the default model
```

Three ways in:

```bash
# 1. headless — run one task and exit (defaults to yolo mode)
python3 -m odysseus -p "add a --json flag to report.py and a test for it" -d ./repo

# 2. interactive — a prompt loop, safe mode, asks before each write
python3 -m odysseus -d ./repo

# 3. resume — pick up the newest session in the directory after a crash or Ctrl-C
python3 -m odysseus -d ./repo --resume -p "keep going"
```

`--mode {safe,yolo,read-only}`, `--model`, `--max-turns` round out the flags.
In `safe` mode every state-changing tool call pauses for `y/N`; `yolo` runs
everything except the irreversible commands the deny list blocks in all modes;
`read-only` allows only `read_file`, `list_files`, and `grep`.

## Anatomy

Built in five layers, bottom to top:

| Layer | File | Lines | What it does |
|---|---|--:|---|
| **Model I/O** | `provider.py` | 134 | the only place that speaks to Gemini: neutral message format, thought-signature round-trip, retry with backoff |
| | `loop.py` | 76 | the turn loop — call model, run tools in order, feed results back; a tool never crashes the loop |
| **Acting** | `tools.py` | 171 | `Tool`, the `@tool` decorator, and `core_tools` — read/write/edit/bash/list/grep, every path through one directory jail |
| | `security.py` | 59 | `Policy` (read-only / safe / yolo) and the deny list of irreversible shell commands |
| **Context** | `context.py` | 65 | `compact` — fold all but the last few messages into one summary when the transcript outgrows its token budget |
| | `memory.py` | 54 | the standing system prompt plus `ODYSSEUS.md`, the project memory file `remember` appends to |
| | `skills.py` | 57 | `skills/<name>/SKILL.md` folders, advertised by description and loaded in full on demand |
| **Spine** | `session.py` | 75 | every message streamed to a JSONL log; on reload a torn tail is dropped and dangling tool calls are answered |
| | `subagent.py` | 27 | `spawn_agent` — hand a self-contained task to a fresh, depth-capped child harness |
| | `harness.py` | 115 | `Harness` — composes all of the above behind `run(task)` and `resume()` |
| **Front door** | `cli.py` | 101 | `python3 -m odysseus`: headless and interactive, event streaming, the safe-mode approver |
| | `fleet.py` | 30 | `run_fleet` — many harnesses across a thread pool, results in input order |

## Compose your own

`Harness` takes `extra_tools`; a plain function becomes a tool with the
`@tool` decorator (every parameter is string-typed — the tool converts):

```python
import datetime
from odysseus import Harness, tool

@tool("Return the current UTC time as an ISO-8601 string.")
def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

harness = Harness(workdir="./sandbox", extra_tools=[utc_now])
print(harness.run("Write now.txt containing the current UTC time. Use utc_now."))
```

Run a batch of them concurrently, one directory each:

```python
from odysseus import Harness, run_fleet

def make_harness(workdir):
    return Harness(workdir=workdir, max_turns=200)

jobs = [
    {"name": "api",  "workdir": "./out/api",  "task": "Build a FastAPI todo service with tests."},
    {"name": "cli",  "workdir": "./out/cli",  "task": "Build a `todo` CLI with argparse and JSON storage."},
]
for result in run_fleet(jobs, make_harness):
    print(result["name"], "ok" if result["ok"] else "FAILED", "-", result["report"][:80])
```
