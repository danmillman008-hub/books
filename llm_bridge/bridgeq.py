"""Agent-side helper for the bridge queue.
  python llm_bridge/bridgeq.py list                 # pending requests (key, size, first user line)
  python llm_bridge/bridgeq.py show KEY [--sys]     # print the request messages (system prompt only with --sys)
  python llm_bridge/bridgeq.py answer KEY FILE      # write answer (FILE='-' = stdin)
"""
import json, sys
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent / "study" / "llm_bridge"
P, A = BASE / "pending", BASE / "answers"

def txt(c):
    return c if isinstance(c, str) else "\n".join(p.get("text", "") for p in (c or []) if isinstance(p, dict))

cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
if cmd == "list":
    for f in sorted(P.glob("*.json"), key=lambda f: f.stat().st_mtime):
        r = json.loads(f.read_text())["request"]; ms = r.get("messages", [])
        last = txt(ms[-1]["content"]) if ms else ""
        print(f.stem, len(json.dumps(r, ensure_ascii=False)), "|", [m["role"] for m in ms], "|", last[:120].replace("\n", " "))
elif cmd == "show":
    r = json.loads((P / f"{sys.argv[2]}.json").read_text())["request"]
    for m in r.get("messages", []):
        if m["role"] == "system" and "--sys" not in sys.argv:
            print(f"=== system ({len(txt(m['content']))} chars, hidden)"); continue
        print(f"=== {m['role']}\n{txt(m['content'])}")
    if r.get("response_format"): print("=== response_format:", r["response_format"])
elif cmd == "answer":
    data = sys.stdin.read() if sys.argv[3] == "-" else Path(sys.argv[3]).read_text()
    (A / f"{sys.argv[2]}.txt").write_text(data, encoding="utf-8"); print("answered", sys.argv[2])
elif cmd == "input":   # only the ---Input Text--- block of an extraction request
    for key in sys.argv[2:]:
        r = json.loads((P / f"{key}.json").read_text())["request"]
        u = txt(r["messages"][-1]["content"])
        seg = u.rsplit("---Input Text---", 1)[-1].replace("---Output---","")
        print(f"######## {key}\n{seg.strip()[:9000]}\n")
