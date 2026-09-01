"""The tool layer: what the model can actually do.

A ``Tool`` is a name, a provider ``spec`` (the ``{"schema": ...}`` the model
sees), and a ``run`` callable. ``core_tools()`` returns the six that make an
agent able to build software: read, write, edit, shell, list, grep.

Design rules embodied here:
- Every tool argument is string-typed. Models emit function arguments as JSON
  strings, so the tools convert (``int``, ``float``) rather than trusting the
  schema to coerce for them.
- Filesystem access is confined to one directory. Every path the file tools
  touch passes through ``resolve()``, which raises ``PermissionError`` the
  moment a realpath lands outside the working directory.
- A tool never raises for an ordinary failure the model could fix. A missing
  snippet, an unreadable file during a walk, output too large to return --
  each comes back as a string the model can read and act on.
"""

import fnmatch
import inspect
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv"}


@dataclass
class Tool:
    """A callable the model can invoke: name, provider spec, and body."""

    name: str
    spec: dict
    run: Callable


def tool(description, **params):
    """Wrap a plain function as a ``Tool``, deriving its schema from the signature.

    Each parameter becomes a string-typed property described by the matching
    keyword argument here; parameters without a default are marked required.
    """
    def decorate(fn):
        signature = inspect.signature(fn).parameters
        properties = {name: {"type": "string", "description": params.get(name, "")}
                      for name in signature}
        required = [name for name, p in signature.items()
                    if p.default is inspect.Parameter.empty]
        schema = {"name": fn.__name__, "description": description,
                  "parameters": {"type": "object", "properties": properties,
                                 "required": required}}
        return Tool(fn.__name__, {"schema": schema}, fn)
    return decorate


def core_tools(workdir):
    """Return the six filesystem/shell tools, each confined to ``workdir``."""
    root = os.path.realpath(workdir)

    def resolve(path):
        """Realpath ``path`` under the working directory, or raise PermissionError."""
        full = os.path.realpath(os.path.join(root, path))
        # The realpath must be the root itself or sit beneath it; a ``..`` or a
        # symlink that climbs out is exactly what this refuses.
        if full != root and not full.startswith(root + os.sep):
            raise PermissionError("%r escapes the working directory" % (path,))
        return full

    @tool("Read a text file; each line is returned as '<lineno>\\t<line>'.",
          path="Path relative to the working directory")
    def read_file(path):
        with open(resolve(path), "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
        body = "\n".join("%d\t%s" % (n, ln)
                         for n, ln in enumerate(lines[:4000], 1))
        if len(lines) > 4000:
            body += "\n... truncated: showing 4000 of %d lines" % len(lines)
        return body

    @tool("Create or overwrite a file, making parent directories as needed.",
          path="Path relative to the working directory",
          content="Full new contents of the file")
    def write_file(path, content):
        full = resolve(path)
        os.makedirs(os.path.dirname(full) or root, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
        return "Wrote %d chars to %s" % (len(content), path)

    @tool("Replace one exact, unique snippet in a file.",
          path="Path relative to the working directory",
          old="Exact text to replace; must occur exactly once",
          new="Replacement text")
    def edit_file(path, old, new):
        full = resolve(path)
        with open(full, "r", encoding="utf-8") as handle:
            text = handle.read()
        # Uniqueness is the contract: refuse a zero- or multi-match edit so the
        # model must disambiguate rather than change the wrong line.
        seen = text.count(old)
        if seen == 0:
            return "ERROR: snippet not found — read the file and copy it exactly"
        if seen > 1:
            return ("ERROR: snippet appears %d times — include more context to "
                    "make it unique" % seen)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text.replace(old, new, 1))
        return "Edited %s" % path

    @tool("Run a shell command in the working directory and return its output.",
          command="Shell command line",
          timeout="Seconds before the command is killed (default 120)")
    def bash(command, timeout="120"):
        try:
            done = subprocess.run(command, shell=True, cwd=root, text=True,
                                  capture_output=True, timeout=float(timeout))
        except subprocess.TimeoutExpired:
            return "ERROR: timed out after %ss" % timeout
        out = (done.stdout or "") + (done.stderr or "")
        if len(out) > 12000:  # keep the head and tail, drop the middle
            out = (out[:6000] + "\n... [%d chars omitted] ...\n"
                   % (len(out) - 12000) + out[-6000:])
        if not out.strip():
            return "(exit %d, no output)" % done.returncode
        return out

    @tool("List files under the working directory matching a glob.",
          pattern="Glob tested against each relative path and basename")
    def list_files(pattern="**/*"):
        found = []
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for name in files:
                rel = os.path.relpath(os.path.join(base, name), root)
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
                    found.append(rel)
        found.sort()
        body = "\n".join(found[:500])
        if len(found) > 500:
            body += "\n... and %d more" % (len(found) - 500)
        return body

    @tool("Search file contents by regular expression.",
          regex="Python regular expression",
          pattern="Only search files whose path or basename matches this glob")
    def grep(regex, pattern="*"):
        compiled = re.compile(regex)
        hits = []
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for name in sorted(files):
                rel = os.path.relpath(os.path.join(base, name), root)
                if not (fnmatch.fnmatch(rel, pattern)
                        or fnmatch.fnmatch(name, pattern)):
                    continue
                try:
                    with open(os.path.join(base, name), "r", encoding="utf-8",
                              errors="replace") as handle:
                        for n, line in enumerate(handle, 1):
                            if compiled.search(line):
                                hits.append("%s:%d: %s"
                                            % (rel, n, line.rstrip()[:200]))
                                if len(hits) >= 200:
                                    return "\n".join(hits)
                except OSError:
                    continue  # unreadable file: skip, do not abort the search
        return "\n".join(hits)

    return [read_file, write_file, edit_file, bash, list_files, grep]
