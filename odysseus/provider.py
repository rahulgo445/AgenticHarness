"""Day 1 -- the provider seam.

Concept: one function, ``complete()``, is the only place Odysseus talks to a
language model. Everything above it works in a small neutral message format
and never sees Gemini's wire shape.

Design rules embodied here:
- The neutral format is the contract. ``_to_wire()`` is the single point where
  neutral messages become Gemini ``contents``; response parsing is the single
  point back. No other module builds or reads provider JSON.
- Gemini 3 requires every replayed ``functionCall`` to carry the exact
  ``thoughtSignature`` the model emitted with it. We store it on the tool call
  and echo it back; skipping the round-trip breaks multi-turn tool use.
- Retries are the provider's job. Transient HTTP and network failures back off
  and retry; every other failure raises with a short, readable message.
"""

import json
import os
import time
import urllib.error
import urllib.request

API_ROOT = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-3.1-pro-preview"


def api_key():
    """Return ODYSSEUS_API_KEY, else GEMINI_API_KEY, else raise RuntimeError.

    ODYSSEUS_API_KEY wins so a throwaway key can be used without disturbing
    other tools that read GEMINI_API_KEY.
    """
    key = os.environ.get("ODYSSEUS_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("No Gemini API key: set ODYSSEUS_API_KEY "
                           "(preferred) or GEMINI_API_KEY.")
    return key


def complete(model, system, messages, tools):
    """Call the model once; return a neutral result dict.

    Shape: ``{"text": str, "tool_calls": [{"name", "args", "signature"}],
    "usage": {"input": int, "output": int}}``. ``tools``, when non-empty, is a
    list of spec dicts (each ``{"schema": ...}``) whose schemas go to Gemini
    as one ``functionDeclarations`` block.
    """
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": _to_wire(messages),
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 65536},
    }
    if tools:
        body["tools"] = [{"functionDeclarations": [t["schema"] for t in tools]}]
    raw = _post("%s/%s:generateContent?key=%s" % (API_ROOT, model, api_key()),
                body)

    text_parts, tool_calls = [], []
    candidates = raw.get("candidates") or [{}]
    for part in candidates[0].get("content", {}).get("parts", []):
        if part.get("thought"):
            continue  # a reasoning-trace part is not answer text
        if "text" in part:
            text_parts.append(part["text"])
        if "functionCall" in part:
            fc = part["functionCall"]
            # thoughtSignature rides on the part, beside functionCall, not
            # inside it; keep it for _to_wire to echo next turn.
            tool_calls.append({"name": fc.get("name"),
                               "args": fc.get("args") or {},
                               "signature": part.get("thoughtSignature")})

    usage = raw.get("usageMetadata", {})
    return {"text": "".join(text_parts), "tool_calls": tool_calls,
            "usage": {"input": usage.get("promptTokenCount", 0),
                      "output": usage.get("candidatesTokenCount", 0)}}


def _to_wire(messages):
    """Map neutral messages to Gemini ``contents``.

    user -> role "user", one text part. assistant -> role "model", a text part
    only when non-empty, then one ``functionCall`` part per tool call, each
    echoing its stored ``thoughtSignature`` (required on replay). tool -> role
    "user", one ``functionResponse`` part wrapping the text as
    ``{"result": text}``.
    """
    wire = []
    for msg in messages:
        role = msg["role"]
        if role == "user":
            wire.append({"role": "user", "parts": [{"text": msg["text"]}]})
        elif role == "assistant":
            parts = [{"text": msg["text"]}] if msg.get("text") else []
            for call in msg.get("tool_calls") or []:
                part = {"functionCall": {"name": call["name"],
                                         "args": call.get("args") or {}}}
                if call.get("signature"):
                    part["thoughtSignature"] = call["signature"]
                parts.append(part)
            wire.append({"role": "model", "parts": parts})
        elif role == "tool":
            wire.append({"role": "user", "parts": [{"functionResponse": {
                "name": msg["name"],
                "response": {"result": msg["text"]}}}]})
    return wire


def _post(url, body, retries=5):
    """POST ``body`` as JSON, return parsed JSON.

    HTTP 429/500/502/503 and transient URLError/TimeoutError sleep
    ``2 ** attempt * 2`` seconds and retry. Other HTTP errors raise
    RuntimeError with the status and the first 400 chars of the error body.
    """
    data = json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise RuntimeError("Gemini HTTP %s: %s" % (exc.code, detail))
        except (urllib.error.URLError, TimeoutError):
            if attempt >= retries - 1:
                raise
            time.sleep(2 ** attempt * 2)
    raise RuntimeError("unreachable: retries exhausted without returning")
