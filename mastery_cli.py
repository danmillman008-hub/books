"""Drive DeepTutor's Mastery Path engine without an LLM: the human/agent plays the model
and calls the real mastery_* tools. Usage:
  ./mp <tool_name> '<json kwargs>'      e.g. ./mp mastery_status '{}'
  ./mp tools                            list tools
Path id defaults to 'zist' (env MP_PATH). Store lives in study/mastery (in-repo)."""
import asyncio, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
STORE = ROOT / "study" / "mastery"
import deeptutor.learning.storage as st
_orig = st.LearningStore.__init__
def _init(self, root=None): _orig(self, root or STORE)
st.LearningStore.__init__ = _init
from deeptutor.capabilities.mastery import tools as T
from deeptutor.core.tool_protocol import BaseTool

def all_tools():
    out = {}
    for v in vars(T).values():
        if isinstance(v, type) and issubclass(v, BaseTool) and v is not BaseTool:
            try: out[v().get_definition().name] = v
            except Exception: pass
    return out

async def main():
    tools = all_tools()
    if len(sys.argv) < 2 or sys.argv[1] == "tools":
        print("\n".join(sorted(tools))); return
    name = sys.argv[1]
    kw = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    kw.setdefault("_mastery_path_id", os.environ.get("MP_PATH", "zist"))
    kw.setdefault("_session_id", ""); kw.setdefault("_turn_id", "")
    if "_mastery_session_mode" not in kw and os.environ.get("MP_MODE"):
        kw["_mastery_session_mode"] = os.environ["MP_MODE"]
    r = await tools[name]().execute(**kw)
    print(("OK " if r.success else "FAIL ") + str(r.content))
asyncio.run(main())
