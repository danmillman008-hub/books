"""Agent-as-LLM bridge: an OpenAI-compatible server for DeepTutor with no API key.

* POST /v1/chat/completions: every request is saved to
  study/llm_bridge/pending/<key>.json, then the server WAITS until an answer
  appears in study/llm_bridge/answers/<key>.txt. The agent (the human-in-the-loop
  "model") writes those answers. Answers are kept forever, so a re-run of any
  pipeline is served from them instantly (deterministic replay / audit log).
* POST /v1/embeddings: a real local embedding model (fastembed, multilingual
  MiniLM-L12, 384-d, CPU) — deterministic, no human involved.
* GET  /v1/models

Run:  DeepTutor/.venv/bin/python llm_bridge/server.py   (port 8765, 127.0.0.1)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

ROOT = Path(__file__).resolve().parent.parent
BASE = Path(os.environ.get("BRIDGE_DIR", ROOT / "study" / "llm_bridge"))
PENDING, ANSWERS = BASE / "pending", BASE / "answers"
for d in (PENDING, ANSWERS):
    d.mkdir(parents=True, exist_ok=True)
CHAT_MODEL = "agent-tutor"
EMB_MODEL = "local-fa-ngram-hash-1024"
EMB_DIM = 1024
WAIT_SECONDS = int(os.environ.get("BRIDGE_WAIT", "7200"))

app = FastAPI()
_embedder = None


import re
import numpy as np

_FA_MAP = str.maketrans({"ي": "ی", "ك": "ک", "ى": "ی", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا", "ؤ": "و",
                         "\u200c": " ", "\u200d": "", "ـ": ""})
_DIACRITICS = re.compile("[\u064B-\u065F\u0670]")
_SUFFIXES = ("های", "ها", "ترین", "تر", "ی")


def _norm(text: str) -> list[str]:
    t = _DIACRITICS.sub("", (text or "").translate(_FA_MAP).lower())
    toks = re.findall(r"[\w]+", t)
    out = []
    for w in toks:
        for suf in _SUFFIXES:
            if len(w) > len(suf) + 2 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


def _h(s: str) -> tuple[int, float]:
    d = hashlib.blake2b(s.encode(), digest_size=8).digest()
    v = int.from_bytes(d, "little")
    return v % EMB_DIM, (1.0 if (v >> 63) & 1 else -1.0)


def embed_text(text: str) -> list[float]:
    """Deterministic lexical embedding: hashed word unigrams/bigrams + char 3-5 grams
    (signed feature hashing, sublinear tf, L2 norm). Persian-normalised."""
    vec = np.zeros(EMB_DIM, dtype=np.float32)
    words = _norm(text)
    feats: dict[str, float] = {}
    for i, w in enumerate(words):
        feats["w:" + w] = feats.get("w:" + w, 0) + 1.0
        if i + 1 < len(words):
            k = "b:" + w + "_" + words[i + 1]
            feats[k] = feats.get(k, 0) + 1.0
        pw = f"<{w}>"
        for n in (3, 4, 5):
            for j in range(max(1, len(pw) - n + 1)):
                k = f"c{n}:" + pw[j:j + n]
                feats[k] = feats.get(k, 0) + 0.5
    for k, c in feats.items():
        idx, sign = _h(k)
        vec[idx] += sign * (1.0 + np.log(c)) * (2.0 if k.startswith("w:") else 1.0)
    n = float(np.linalg.norm(vec))
    if n == 0:
        vec[0] = 1.0; n = 1.0
    return (vec / n).tolist()


class _Embedder:
    def embed(self, texts):
        return [np.asarray(embed_text(t)) for t in texts]


def _get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = _Embedder()
    return _embedder


def _content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    return str(content or "")


def request_key(body: dict) -> str:
    canon = {
        "messages": [
            {"role": m.get("role"), "content": _content_text(m.get("content"))}
            for m in body.get("messages", [])
        ],
        "response_format": body.get("response_format"),
        "tools": body.get("tools"),
    }
    return hashlib.sha256(json.dumps(canon, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]


def _parse_answer(raw: str) -> dict:
    """Answer file: plain text, or JSON {"content":..., "tool_calls":[...]}."""
    s = raw.strip()
    if s.startswith("{") and '"__bridge__"' in s:
        return json.loads(s)
    return {"content": raw}


async def _await_answer(key: str, body: dict) -> dict:
    ans = ANSWERS / f"{key}.txt"
    if not ans.exists():
        pend = PENDING / f"{key}.json"
        if not pend.exists():
            pend.write_text(
                json.dumps({"key": key, "created": time.time(), "request": body}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        deadline = time.time() + WAIT_SECONDS
        while not ans.exists():
            if time.time() > deadline:
                raise TimeoutError(key)
            await asyncio.sleep(1.0)
        await asyncio.sleep(0.2)  # let the writer finish
        pend.unlink(missing_ok=True)
    return _parse_answer(ans.read_text(encoding="utf-8"))


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [
        {"id": CHAT_MODEL, "object": "model", "owned_by": "agent"},
        {"id": EMB_MODEL, "object": "model", "owned_by": "local"},
    ]}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    body = await req.json()
    key = request_key(body)
    try:
        ans = await _await_answer(key, body)
    except TimeoutError:
        return JSONResponse({"error": {"message": f"agent did not answer {key}", "type": "timeout"}}, 504)
    content = ans.get("content") or ""
    tool_calls = ans.get("tool_calls")
    cid = "chatcmpl-" + uuid.uuid4().hex[:12]
    usage = {"prompt_tokens": 0, "completion_tokens": len(content) // 3, "total_tokens": len(content) // 3}
    if body.get("stream"):
        async def gen():
            delta = {"role": "assistant", "content": content}
            if tool_calls:
                delta["tool_calls"] = [dict(tc, index=i) for i, tc in enumerate(tool_calls)]
            chunk = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                     "model": CHAT_MODEL, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            end = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": CHAT_MODEL,
                   "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls" if tool_calls else "stop"}],
                   "usage": usage}
            yield f"data: {json.dumps(end, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(gen(), media_type="text/event-stream")
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"id": cid, "object": "chat.completion", "created": int(time.time()), "model": CHAT_MODEL,
            "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if tool_calls else "stop"}],
            "usage": usage}


@app.post("/v1/embeddings")
@app.post("/v1/embeddings/embeddings")
async def embeddings(req: Request):
    body = await req.json()
    inp = body.get("input")
    texts = [inp] if isinstance(inp, str) else list(inp or [])
    vecs = await asyncio.to_thread(lambda: [v.tolist() for v in _get_embedder().embed(texts)])
    return {"object": "list", "model": EMB_MODEL,
            "data": [{"object": "embedding", "index": i, "embedding": v} for i, v in enumerate(vecs)],
            "usage": {"prompt_tokens": 0, "total_tokens": 0}}


if __name__ == "__main__":
    _get_embedder()
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("BRIDGE_PORT", "8765")), log_level="warning")
