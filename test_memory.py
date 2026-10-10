"""Usage (from the project folder):  python test_memory.py
PLUMBING TEST with a scripted stand-in for Gemini (no internet, no real Gemini call).
Checks: short-term memory (conversation), long-term memory (history), the instructions being re-sent,
and that memory stays OFF for the evaluation harness. Real behaviour comes from chat_gateway_agent.py."""
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, ".")
os.environ["GEMINI_WAIT_S"] = "0"
os.environ["GEMINI_ATTEMPTS"] = "1"

from app.agent import gateway_agent
from app.agent.gateway_agent import GatewayAgent, build_instruction
from app.agent.memory_store import MemoryStore
from app.agent.tool_gateway import ToolGateway, get_tool_definitions
import tools as backend_tools

ToolGateway._knowledge_search = staticmethod(
    lambda args: {"success": True, "status": "FOUND", "message": "Result 1: KB-VPN-001 ...",
                  "data": {"source": "KB-VPN-001_vpn_not_connecting.md", "citation": "KB-VPN-001 (KB-VPN-001_vpn_not_connecting.md)"}})

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


class Step:
    def __init__(self, type, name=None, arguments=None, id=None):
        self.type, self.name, self.arguments, self.id = type, name, arguments, id


class Interaction:
    def __init__(self, id, steps, output_text=""):
        self.id, self.steps, self.output_text = id, steps, output_text


class PlaybookGemini:
    """Stand-in for Gemini's VPN playbook (NOT an AI). Records every call it receives."""
    def __init__(self, refuse_instruction_on_followup=False):
        self.n, self.user, self.calls, self.interactions = 0, None, [], self
        self.awaiting_username = False
        self.refuse = refuse_instruction_on_followup

    def _call(self, name, args):
        self.n += 1
        return Interaction(f"i{self.n}", [Step("function_call", name, args, f"c{self.n}")])

    def _text(self, text):
        self.n += 1
        return Interaction(f"i{self.n}", [Step("text")], text)

    def _after_username(self, tool_names):
        if "lookup_user_history" in tool_names:
            return self._call("lookup_user_history", {"username": self.user})
        return self._call("check_vpn_status", {"username": self.user})

    def create(self, **kw):
        self.calls.append(kw)
        if self.refuse and "previous_interaction_id" in kw and "system_instruction" in kw:
            raise RuntimeError("Error code: 400 - system_instruction is not supported with previous_interaction_id")
        tool_names = [t["name"] for t in kw.get("tools", [])]
        data = kw["input"]
        if isinstance(data, str):                                   # a user message
            m = re.search(r"(?:username(?: is)?|i'?m)\s+(\w+)", data, re.I)
            if m:
                self.user = m.group(1).lower()
            elif self.awaiting_username and "previous_interaction_id" in kw:
                self.user = data.strip().lower()
            if not self.user:
                self.awaiting_username = True
                return self._text("Please tell me your username.")
            self.awaiting_username = False
            return self._after_username(tool_names)
        last = json.loads(data[0]["result"][0]["text"])             # a tool result
        name, status = data[0]["name"], last["status"]
        if name == "lookup_user_history":
            return self._call("check_vpn_status", {"username": self.user})
        if status == "INACTIVE":
            return self._call("restart_vpn", {"username": self.user})
        if status == "VPN_RESTARTED":
            return self._text("Your VPN has been restored.")
        if status == "RESTART_FAILED":
            return self._call("create_support_ticket", {"username": self.user, "category": "vpn", "summary": "VPN restart failed"})
        if status == "TICKET_CREATED":
            return self._call("escalate_incident", {"ticket_id": last["data"]["ticket_id"], "reason": "VPN restart failed"})
        return self._text("I have escalated this to Tier-2 support.")


def new_db():
    return MemoryStore(Path(tempfile.mkdtemp()) / "memory.db")


def agent_for(client, memory=None):
    backend_tools.reset_state()
    return GatewayAgent(client=client, model="stand-in", memory=memory)


# ---------------- instructions are sent on every call ----------------
g = PlaybookGemini()
a = agent_for(g)
a.run("Hi, my username is thabo. My VPN isn't working.", verbose=False)
check("instructions are sent on EVERY Gemini call", len(g.calls) >= 3 and all("system_instruction" in c for c in g.calls),
      f"({len(g.calls)} calls)")

g = PlaybookGemini(refuse_instruction_on_followup=True)
a = agent_for(g)
reply = a.run("Hi, my username is thabo. My VPN isn't working.", verbose=False)
check("if the API refuses instructions on follow-ups, the agent adapts and still finishes", "restored" in reply.lower(), reply)

# ---------------- short-term memory ----------------
g = PlaybookGemini()
a = agent_for(g)
r1 = a.run("My VPN isn't working.", verbose=False)
first_id = a.last_interaction_id
r2 = a.run("thabo", verbose=False)
check("turn 1 asks for the username", "username" in r1.lower() and first_id is not None)
check("turn 2 continues the SAME conversation", any(c.get("previous_interaction_id") == first_id and isinstance(c["input"], str) for c in g.calls))
check("the answer to the question completes the task", "restored" in r2.lower() and backend_tools.STATE["users"]["thabo"]["vpn"] == "active")
a.new_conversation()
check("new_conversation() forgets the conversation", a.last_interaction_id is None)

# ---------------- long-term memory ----------------
mem = new_db()
mem.record("Sipho", "vpn", "fix_failed", detail="restart failed")
mem.record("thabo", "vpn", "fixed", detail="restarted")
mem.record("sipho", "vpn", "ticket_created", ticket_ref="INC-1001", detail="VPN restart failed")
rows = mem.history("SIPHO")
check("history is per user, newest first, case-insensitive", [r["event"] for r in rows] == ["ticket_created", "fix_failed"], str([r["event"] for r in rows]))
check("history respects the limit", len(mem.history("sipho", limit=1)) == 1)
mem2 = MemoryStore(mem.path)
check("history survives a restart (stored on disk)", len(mem2.history("sipho")) == 2)
check("unknown user has no history", mem.history("nobody") == [])

# the agent writes events into memory
mem = new_db()
a = agent_for(PlaybookGemini(), memory=mem)
a.run("Hi, my username is thabo. My VPN isn't working.", verbose=False)
check("a successful fix is remembered", [r["event"] for r in mem.history("thabo")] == ["fixed"], str(mem.history("thabo")))
a = agent_for(PlaybookGemini(), memory=mem)
a.run("Username sipho here, the VPN is down.", verbose=False)
events = [r["event"] for r in mem.history("sipho")]
check("failed fix, ticket and escalation are remembered", events == ["escalated", "ticket_created", "fix_failed"], str(events))
check("the escalation is linked to the right user and ticket", mem.history("sipho")[0]["ticket_ref"] == "INC-1001")

# the history tool
gw = ToolGateway(memory=mem)
found = gw.call_tool("lookup_user_history", {"username": " SIPHO "})
check("history tool: found, newest first", found["status"] == "HISTORY_FOUND" and found["data"]["count"] == 3
      and found["message"].splitlines()[1].split()[1] == "vpn" and found["message"].splitlines()[1].split()[2] == "escalated")
check("history tool: unknown user", gw.call_tool("lookup_user_history", {"username": "zanele"})["status"] == "NO_HISTORY")
check("history tool: bad arguments", gw.call_tool("lookup_user_history", {})["status"] == "BAD_ARGUMENTS")
check("history tool: refuses when memory is off", ToolGateway().call_tool("lookup_user_history", {"username": "x"})["status"] == "MEMORY_OFF")

# the agent can use what it finds
g = PlaybookGemini()
a = agent_for(g, memory=mem)
a.run("Hi, my username is sipho. VPN again.", verbose=False)
check("agent calls the history tool first when memory is on", [s["tool"] for s in a.gateway.steps][:2] == ["knowledge_search", "lookup_user_history"]
      or [s["tool"] for s in a.gateway.steps][0] == "lookup_user_history", str([s["tool"] for s in a.gateway.steps]))

# ---------------- memory stays OFF for the evaluation ----------------
check("memory off: history tool is not offered", "lookup_user_history" not in [t["name"] for t in get_tool_definitions(include_history=False)])
check("memory on: history tool is offered", "lookup_user_history" in [t["name"] for t in get_tool_definitions(include_history=True)])
check("memory off: instructions do not mention it", "lookup_user_history" not in build_instruction(False))
check("memory on: instructions explain it", "lookup_user_history" in build_instruction(True))

calls = []
def harness_call_tool(tool, args=None):
    calls.append(tool); return backend_tools.execute_tool(tool, args or {})
backend_tools.reset_state()
gateway_agent.genai = types.SimpleNamespace(Client=lambda api_key=None: PlaybookGemini())
os.environ["GEMINI_API_KEY"] = "dummy"
before = len(mem.history("thabo"))
gateway_agent.run("Hi, my username is thabo. My VPN isn't working.", harness_call_tool)
check("harness mode: no history tool call, nothing written to memory",
      "lookup_user_history" not in calls and len(mem.history("thabo")) == before, str(calls))

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
