"""Usage (from the project folder):  python test_thoughts.py
PLUMBING TEST with a scripted stand-in for Gemini (no internet). Checks the visible-thought feature:
thoughts are read from Gemini's replies, shown before the action, recorded, switched on/off, and never crash anything."""
import contextlib
import io
import json
import os
import sys
import types

sys.path.insert(0, ".")
os.environ["GEMINI_WAIT_S"], os.environ["GEMINI_ATTEMPTS"] = "0", "1"
os.environ.pop("EVAL_SHOW_THOUGHTS", None)

from app.agent import gateway_agent
from app.agent.gateway_agent import GatewayAgent
import tools as backend_tools

results = []

def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")

class Step:
    def __init__(self, type, **kw):
        self.type = type
        self.__dict__.update(kw)

class Summary:
    def __init__(self, text):
        self.text = text


class Interaction:
    def __init__(self, id, steps, output_text=""):
        self.id, self.steps, self.output_text = id, steps, output_text


class Flow:
    """Plays a fixed list of Gemini replies, in order. Records every call it receives."""
    def __init__(self, rounds, refuse_config=False):
        self.rounds, self.calls, self.interactions, self.n, self.refuse = list(rounds), [], self, 0, refuse_config

    def create(self, **kw):
        self.calls.append(kw)
        if self.refuse and "generation_config" in kw:
            raise RuntimeError("Error code: 400 - unknown field generation_config")
        self.n += 1
        steps, text = self.rounds.pop(0)
        return Interaction(f"i{self.n}", steps, text)


def vpn_flow(thought_step):
    return [([thought_step, Step("function_call", name="check_vpn_status", arguments={"username": "thabo"}, id="c1")], ""),
            ([Step("function_call", name="restart_vpn", arguments={"username": "thabo"}, id="c2")], ""),
            ([Step("text")], "Your VPN has been restored.")]


def agent_for(flow, **kw):
    backend_tools.reset_state()
    return GatewayAgent(client=flow, model="stand-in", **kw)


MESSAGE = "Hi, my username is thabo. My VPN isn't working."
thought = Step("thought", signature="abc", summary=[Summary("**Plan** I will check the VPN status first.")])

# 1. thought is recorded, before the action
flow = Flow(vpn_flow(thought))
a = agent_for(flow, show_thoughts=True)
a.run(MESSAGE, verbose=False)
kinds = [e["kind"] for e in a.events]
check("events: user, thought, action, observation ... final", kinds[:4] == ["user", "thought", "action", "observation"] and kinds[-1] == "final", str(kinds))
check("thought text is readable", "check the VPN status first" in a.events[1]["text"])

# 2. printed before the action
buffer = io.StringIO()
flow = Flow(vpn_flow(thought))
a = agent_for(flow, show_thoughts=True)
with contextlib.redirect_stdout(buffer):
    a.run(MESSAGE)
text = buffer.getvalue()
check("[THOUGHT] is printed before [ACTION]", "[THOUGHT]" in text and text.index("[THOUGHT]") < text.index("[ACTION]"))
check("markdown bold marks are removed from the printed thought", "**" not in text.split("[THOUGHT]")[1].split("[ACTION]")[0])

# 3. summary as a plain dict is also understood
flow = Flow(vpn_flow(Step("thought", summary=[{"text": "Dict form thought."}])))
a = agent_for(flow, show_thoughts=True)
a.run(MESSAGE, verbose=False)
check("thought summary given as a dict is understood", any(e["kind"] == "thought" and "Dict form" in e["text"] for e in a.events))

# 4. a thought with no readable summary (only a signature) is ignored without error
flow = Flow(vpn_flow(Step("thought", signature="only-a-signature")))
a = agent_for(flow, show_thoughts=True)
reply = a.run(MESSAGE, verbose=False)
check("signature-only thought: no thought event, no crash", "restored" in reply.lower() and not any(e["kind"] == "thought" for e in a.events))

# 5. switch on / off: the thinking settings are sent only when on
flow = Flow(vpn_flow(thought))
agent_for(flow, show_thoughts=True).run(MESSAGE, verbose=False)
check("thoughts ON: thinking settings sent on every call", all(c.get("generation_config", {}).get("thinking_summaries") == "auto" for c in flow.calls), f"({len(flow.calls)} calls)")
flow = Flow(vpn_flow(thought))
agent_for(flow, show_thoughts=False).run(MESSAGE, verbose=False)
check("thoughts OFF: thinking settings never sent", not any("generation_config" in c for c in flow.calls))

os.environ.pop("THINKING_LEVEL", None)
flow = Flow(vpn_flow(thought))
agent_for(flow, show_thoughts=True).run(MESSAGE, verbose=False)
check("default thinking level is medium (measured: 3 of 3 summaries, against 1 of 3 at low)",
      all(c["generation_config"]["thinking_level"] == "medium" for c in flow.calls))

# 6. the API refuses the setting: the agent carries on
flow = Flow(vpn_flow(thought), refuse_config=True)
a = agent_for(flow, show_thoughts=True)
reply = a.run(MESSAGE, verbose=False)
check("API refuses thinking settings: agent switches them off and still finishes", "restored" in reply.lower() and a.show_thoughts is False, reply)

# 7. evaluation harness: off by default, on only with EVAL_SHOW_THOUGHTS=1
gateway_agent.genai = types.SimpleNamespace(Client=lambda api_key=None: harness_flow)
os.environ["GEMINI_API_KEY"] = "dummy"
calls_seen = []
def harness_call_tool(tool, args=None):
    return backend_tools.execute_tool(tool, args or {})
backend_tools.reset_state()
harness_flow = Flow(vpn_flow(thought))
gateway_agent.run(MESSAGE, harness_call_tool)
check("evaluation harness: thoughts are OFF by default", not any("generation_config" in c for c in harness_flow.calls))
os.environ["EVAL_SHOW_THOUGHTS"] = "1"
backend_tools.reset_state()
harness_flow = Flow(vpn_flow(thought))
gateway_agent.run(MESSAGE, harness_call_tool)
check("evaluation harness: EVAL_SHOW_THOUGHTS=1 turns them on", all("generation_config" in c for c in harness_flow.calls))
os.environ.pop("EVAL_SHOW_THOUGHTS", None)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
