"""The agent loop.

``run_loop()`` drives the conversation. It asks the model for a reply, runs
whatever tools the model called, feeds the results back, and repeats until
the model answers with no tool calls or the turn budget is spent.

Design rules this file embodies:
- The loop never crashes because a tool did. An unknown tool name or a raised
  exception becomes an ordinary tool-result string that the model can read
  and recover from on the next turn.
- Every side effect is observable and gated. ``on_event()`` reports each
  assistant reply and brackets every tool run; ``before_tool()`` is a policy
  hook that may block a call before it happens.
- ``before_turn()`` is the seam for context management: when a caller supplies
  it, it rewrites the message list in place before each model call so the loop
  keeps its single source of truth. It is inert when left unset.
"""

from . import provider


def run_loop(model, system, messages, tools, on_event, before_tool,
             max_turns=80, before_turn=None):
    """Run the agent loop and return the model's final text answer.

    ``tools`` maps name -> Tool (``.spec`` is a ``{"schema": ...}`` dict,
    ``.run`` a callable taking keyword arguments). ``on_event(kind, payload)``
    fires ``"assistant"`` after each reply and ``"tool_start"`` /
    ``"tool_end"`` around each execution. ``before_tool(call)`` returns None to
    allow or a reason string to block (result ``"BLOCKED: <reason>"``).
    ``before_turn(messages)``, when given, rewrites the list in place before
    each model call.
    """
    specs = [t.spec for t in tools.values()]
    for _ in range(max_turns):
        if before_turn is not None:
            before_turn(messages)  # in-place rewrite; context-compaction seam
        reply = provider.complete(model, system, messages, specs)
        messages.append({"role": "assistant", "text": reply["text"],
                         "tool_calls": reply["tool_calls"]})
        on_event("assistant", reply)
        if not reply["tool_calls"]:
            return reply["text"]
        for call in reply["tool_calls"]:
            result = _run_call(call, tools, on_event, before_tool)
            messages.append({"role": "tool", "name": call["name"],
                             "text": str(result)})

    # Budget spent: force a wrap-up with tools withheld so the model cannot
    # open another round it has no turns left to finish.
    messages.append({"role": "user", "text": "Turn limit reached; wrap up now."})
    final = provider.complete(model, system, messages, [])
    messages.append({"role": "assistant", "text": final["text"],
                     "tool_calls": final["tool_calls"]})
    return final["text"]


def _run_call(call, tools, on_event, before_tool):
    """Execute one tool call, turning every failure mode into a string.

    Blocked by policy -> ``"BLOCKED: <reason>"``. Unknown tool ->
    ``"ERROR: unknown tool <name>"``. Tool raised -> ``"ERROR: <Type>: <msg>"``.
    """
    reason = before_tool(call)
    if reason is not None:
        return "BLOCKED: %s" % reason
    tool = tools.get(call["name"])
    if tool is None:
        return "ERROR: unknown tool %s" % call["name"]
    on_event("tool_start", call)
    try:
        result = tool.run(**(call.get("args") or {}))
    except Exception as exc:  # a tool failure is data for the model, not a crash
        result = "ERROR: %s: %s" % (type(exc).__name__, exc)
    on_event("tool_end", {"call": call, "result": result})
    return result
