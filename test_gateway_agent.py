"""Usage (from the project folder):  python test_gateway_agent.py
PLUMBING TEST ONLY. A tiny scripted stand-in plays the role of Gemini, so no internet and
no real Gemini call is made. It checks the wiring: agent -> gateway -> Mmabotse's tools -> back.
Results of the real Gemini agent come from run_gateway_agent.py and the evaluation, not from here."""
import json
import os
import re
import sys
import types

sys.path.insert(0, ".")
os.environ["GEMINI_WAIT_S"] = "0"
os.environ["GEMINI_ATTEMPTS"] = "2"

from app.agent import gateway_agent
from app.agent.gateway_agent import GatewayAgent, MAX_ROUNDS, EMPTY_TEXT, add_citation, find_ungrounded_teams
from app.agent.tool_gateway import ToolGateway
import tools as backend_tools  # Mmabotse's backend/tools.py (same module the gateway uses)

# keep the test fast and independent of the embedding model
ToolGateway._knowledge_search = staticmethod(
    lambda args: {"success": True, "status": "FOUND", "message": "Source: vpn_troubleshooting.txt ...",
                  "data": {"source": "vpn_troubleshooting.txt", "distance": 0.5}})

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


class ScriptedGemini:
    """Stand-in for Gemini's VPN playbook. NOT an AI: it just reacts to the last tool result."""
    def __init__(self, invent_team=False):
        self.n, self.user, self.interactions, self.invent_team = 0, None, self, invent_team
        self.shown = {}                      # tool name -> exact text sent back to the "model"

    def _call(self, name, args):
        self.n += 1
        return Interaction(f"i{self.n}", [Step("function_call", name, args, f"c{self.n}")])

    def _text(self, text):
        self.n += 1
        return Interaction(f"i{self.n}", [Step("text")], text)

    def create(self, **kw):
        data = kw["input"]
        if isinstance(data, str):                                  # first turn: the user's message
            m = re.search(r"(?:username(?: is)?|i'?m)\s+(\w+)", data, re.I)
            if not m:
                return self._text("Please tell me your username so I can look into this.")
            self.user = m.group(1).lower()
            return self._call("knowledge_search", {"query": "vpn not connecting"})
        last = json.loads(data[0]["result"][0]["text"])            # later turns: tool result comes back
        self.shown[data[0]["name"]] = data[0]["result"][0]["text"]
        name, status = data[0]["name"], last["status"]
        if name == "knowledge_search":
            return self._call("check_vpn_status", {"username": self.user})
        if status == "INACTIVE":
            return self._call("restart_vpn", {"username": self.user})
        if status == "VPN_RESTARTED":
            return self._text("Your VPN has been restored (article: vpn_troubleshooting.txt).")
        if status == "RESTART_FAILED":
            return self._call("create_support_ticket", {"username": self.user, "category": "vpn",
                                                        "summary": "VPN restart failed"})
        if status == "TICKET_CREATED":
            return self._call("escalate_incident", {"ticket_id": last["data"]["ticket_id"], "reason": "VPN restart failed"})
        if self.invent_team:
            return self._text("I have escalated this to the Identity and Access Team.")
        return self._text("I have escalated this to Tier-2 support.")


def fresh_agent(client):
    backend_tools.reset_state()
    return GatewayAgent(client=client, model="stand-in")


# 1. fixable VPN: right tools, in order, state really changed, reply returned
a = fresh_agent(ScriptedGemini())
reply = a.run("Hi, my username is thabo. My VPN isn't working.", verbose=False)
tools_used = [s["tool"] for s in a.gateway.steps]
check("fixable VPN: tool order", tools_used == ["knowledge_search", "check_vpn_status", "restart_vpn"], str(tools_used))
check("fixable VPN: backend state changed", backend_tools.STATE["users"]["thabo"]["vpn"] == "active")
check("fixable VPN: reply returned", "restored" in reply.lower())

# 2. unfixable VPN: failure feeds the next decision -> ticket -> escalation recorded in backend
a = fresh_agent(ScriptedGemini())
reply = a.run("Username sipho here, the VPN is down.", verbose=False)
tools_used = [s["tool"] for s in a.gateway.steps]
check("unfixable VPN: ticket then escalate", tools_used[-2:] == ["create_support_ticket", "escalate_incident"], str(tools_used))
check("unfixable VPN: ticket escalated in backend",
      any(t["status"] == "escalated" for t in backend_tools.STATE["tickets"].values()))

# 3. missing username: asks, calls no tool, changes nothing
a = fresh_agent(ScriptedGemini())
reply = a.run("My VPN isn't working.", verbose=False)
check("missing username: no tool called", a.gateway.steps == [] and "username" in reply.lower())

# 4. every call is in Mmabotse's audit log too
a = fresh_agent(ScriptedGemini())
a.run("Hi, my username is thabo. My VPN isn't working.", verbose=False)
logged = [e["tool"] for e in backend_tools.STATE["audit_log"]]
check("backend audit log has the tool calls", logged == ["check_vpn_status", "restart_vpn"], str(logged))

# 5. runaway agent is stopped
class Looping:
    def __init__(self): self.interactions, self.n = self, 0
    def create(self, **kw):
        self.n += 1
        return Interaction(f"i{self.n}", [Step("function_call", "check_vpn_status", {"username": "thabo"}, f"c{self.n}")])
a = fresh_agent(Looping())
reply = a.run("Hi, my username is thabo.", verbose=False)
check("runaway agent is stopped", len(a.gateway.steps) == MAX_ROUNDS and "could not finish" in reply.lower(),
      f"({len(a.gateway.steps)} steps)")

# 6. Gemini down: clean message, no crash
class Down:
    def __init__(self): self.interactions = self
    def create(self, **kw): raise RuntimeError("Error code: 503 - high demand")
a = fresh_agent(Down())
reply = a.run("Hi, my username is thabo.", verbose=False)
check("Gemini down: clean message, nothing changed", "not responding" in reply.lower() and a.gateway.steps == [])

# 7. the interface Mmabotse's harness uses:  run(message, call_tool)
calls = []
def harness_call_tool(tool, args=None):
    calls.append(tool); return backend_tools.execute_tool(tool, args or {})
backend_tools.reset_state()
gateway_agent.genai = types.SimpleNamespace(Client=lambda api_key=None: ScriptedGemini())
os.environ["GEMINI_API_KEY"] = "dummy"
reply = gateway_agent.run("Hi, my username is thabo. My VPN isn't working.", harness_call_tool)
check("harness interface: backend calls go through the harness's call_tool, knowledge search does not",
      calls == ["check_vpn_status", "restart_vpn"] and "restored" in reply.lower(), str(calls))

# 8. knowledge-base article line is added by code when the model forgot it
a = fresh_agent(ScriptedGemini())
reply = a.run("Hi, my username is thabo. My VPN isn't working.", verbose=False)
check("code adds the closest match when the model names no article", reply.rstrip().endswith("Closest knowledge base match: vpn_troubleshooting.txt"))
check("add_citation: not duplicated", add_citation("Done.\nKnowledge base article: a.txt", ["a.txt"]) == "Done.\nKnowledge base article: a.txt")
check("add_citation: not added when the model named its own article", add_citation("Done.\nKnowledge base article: KB-VPN-001", ["KB-VPN-003"]) == "Done.\nKnowledge base article: KB-VPN-001")
check("add_citation: nothing retrieved, nothing added", add_citation("Please give your username.", []) == "Please give your username.")

# 9. invented team names are detected
a = fresh_agent(ScriptedGemini())
a.run("Username sipho here, the VPN is down.", verbose=False)
check("grounded answer: no warning", a.warnings == [], str(a.warnings))
a = fresh_agent(ScriptedGemini(invent_team=True))
a.run("Username sipho here, the VPN is down.", verbose=False)
check("invented team: warning raised", len(a.warnings) == 1 and "Identity and Access Team" in a.warnings[0], str(a.warnings))
tool_said = "inc-1001 escalated to tier-2 support."
check("find_ungrounded_teams: parenthesis form", find_ungrounded_teams("escalated to Tier-2 support (Print Services Team).", tool_said) == ["Print Services Team"])
check("find_ungrounded_teams: 'the ... Team' form", find_ungrounded_teams("sent to the Identity and Access Team", tool_said) == ["Identity and Access Team"])
check("find_ungrounded_teams: grounded text is fine", find_ungrounded_teams("escalated to Tier-2 support.", tool_said) == [])

# 10. real answers from the live runs are caught; the model is told to report the team exactly
tool_said = "inc-1001 escalated to tier-2 support."
check("real printer answer (extra team in brackets) is flagged",
      find_ungrounded_teams("escalated it directly to Tier-2 support (Print Services / Onsite Maintenance) so a technician can attend.", tool_said)
      == ["Print Services / Onsite Maintenance"])
check("real sipho answer (slash form) is flagged once",
      find_ungrounded_teams("escalated it to Tier-2 support / the Identity and Access Team for further investigation into the gateway issue.", tool_said)
      == ["Identity and Access Team"])
check("plain 'Tier-2 support' is not flagged",
      find_ungrounded_teams("I have escalated it to Tier-2 support so they can investigate.", tool_said) == [])
fake = ScriptedGemini()
a = fresh_agent(fake)
a.run("Username sipho here, the VPN is down.", verbose=False)
check("model is told to report the team exactly", "No other team" in fake.shown.get("escalate_incident", ""))
check("backend result itself is unchanged by the note", "note" not in a.gateway.steps[-1] and a.gateway.steps[-1]["status"] == "ESCALATED")

# 11. empty or odd Gemini replies must not crash the agent (a crash like this was found in the real evaluation, scenario S13)
class NoSteps:
    """A reply whose steps are None and whose output_text fails like the SDK property might."""
    id = "x"
    steps = None
    @property
    def output_text(self):
        raise TypeError("'NoneType' object is not iterable")

class Odd:
    def __init__(self, replies):
        self.replies, self.interactions, self.calls = list(replies), self, 0
    def create(self, **kw):
        self.calls += 1
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

odd = Odd([NoSteps()])
a = fresh_agent(odd)
try:
    reply = a.run("I'm thabo and the printer isn't working.", verbose=False); crashed = False
except Exception as e:
    reply, crashed = repr(e), True
check("always-empty reply: clean message, no crash, asked twice", not crashed and reply == EMPTY_TEXT and odd.calls == 2, f"({odd.calls} calls) {reply[:60]}")

odd = Odd([NoSteps(), Interaction("i2", [Step("text")], "Which printer is it?")])
a = fresh_agent(odd)
reply = a.run("I'm thabo and the printer isn't working.", verbose=False)
check("empty reply then a good one: the second ask is used", reply == "Which printer is it?" and odd.calls == 2, f"({odd.calls} calls)")

class StepsNoneWithText:
    id, steps, output_text = "y", None, "Please give me the printer ID."
odd = Odd([StepsNoneWithText()])
a = fresh_agent(odd)
reply = a.run("I'm thabo and the printer isn't working.", verbose=False)
check("reply with no steps but with text is accepted", reply == "Please give me the printer ID." and odd.calls == 1)

# 12. a missing user or printer is reported with the plain words "not found"
from app.agent.gateway_agent import BASE_INSTRUCTION
check("instructions: a missing user or printer is reported as 'not found', then the agent stops",
      "was not found" in BASE_INSTRUCTION and "stop. Change nothing" in BASE_INSTRUCTION)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
