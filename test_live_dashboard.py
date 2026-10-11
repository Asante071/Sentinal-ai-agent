"""Usage (from the project folder):  python test_live_dashboard.py
Tests the live console's server with a scripted stand-in for Gemini (no internet, no real Gemini call)."""
import json
import os
import sys
import tempfile
import threading
import time
import types
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
os.environ["GEMINI_WAIT_S"], os.environ["GEMINI_ATTEMPTS"] = "0", "1"

from app.agent.gateway_agent import GatewayAgent
from app.agent.memory_store import MemoryStore
from app.agent.tool_gateway import ToolGateway
from app.live_dashboard import PAGE, Console, make_server, offline_events, outcome_of, parse_articles
import tools as backend_tools

results = []


def check(name, condition, detail=""):
    results.append(bool(condition))
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")


KB_MESSAGE = ("Result 1: KB-VPN-001 (KB-VPN-001_vpn_not_connecting.md), distance 0.7592\n\n# VPN will not connect\n\n---\n\n"
              "Result 2: KB-VPN-002 (KB-VPN-002_vpn_slow_or_dropping.md), distance 0.8951\n\n# VPN is slow")
ToolGateway._knowledge_search = staticmethod(lambda args: {
    "success": True, "status": "FOUND", "message": KB_MESSAGE,
    "data": {"source": "KB-VPN-001_vpn_not_connecting.md", "citation": "KB-VPN-001 (KB-VPN-001_vpn_not_connecting.md)"}})


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
    """Plays a fixed list of Gemini replies. The first reply can be delayed so 'busy' can be observed."""
    def __init__(self, rounds, delay=0.0):
        self.rounds, self.interactions, self.n, self.delay = list(rounds), self, 0, delay

    def create(self, **kw):
        if self.n == 0 and self.delay:
            time.sleep(self.delay)
        self.n += 1
        steps, text = self.rounds.pop(0)
        return Interaction(f"i{self.n}", steps, text)


def call(step_id, name, args):
    return Step("function_call", name=name, arguments=args, id=step_id)


thought = Step("thought", summary=[Summary("**Plan** I will check the VPN status first.")])
sipho_flow = [
    ([thought, call("c0", "knowledge_search", {"query": "vpn down"})], ""),
    ([call("c1", "check_vpn_status", {"username": "sipho"})], ""),
    ([call("c2", "restart_vpn", {"username": "sipho"})], ""),
    ([call("c3", "create_support_ticket", {"username": "sipho", "category": "vpn", "summary": "VPN restart failed"})], ""),
    ([call("c4", "escalate_incident", {"ticket_id": "INC-1001", "reason": "VPN restart failed"})], ""),
    ([Step("text")], "I created ticket **INC-1001** and escalated it to Tier-2 support.\nKnowledge base article: KB-VPN-001 (KB-VPN-001_vpn_not_connecting.md)"),
]
thabo_flow = [
    ([call("d1", "check_vpn_status", {"username": "thabo"})], ""),
    ([call("d2", "restart_vpn", {"username": "thabo"})], ""),
    ([Step("text")], "Your VPN has been restored."),
]

backend_tools.reset_state()
memory = MemoryStore(Path(tempfile.mkdtemp()) / "memory.db")
agent = GatewayAgent(client=Flow(sipho_flow, delay=0.5), model="stand-in", memory=memory, show_thoughts=True)
console = Console(agent, memory)
server = make_server(console, 0)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = f"http://127.0.0.1:{server.server_address[1]}"


def request(path, body=None, base=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request((base or BASE) + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if r.headers.get("Content-Type", "").startswith("application/json") else raw)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def wait_until_idle(limit=15):
    end = time.time() + limit
    while time.time() < end:
        if not request("/api/state?since=0")[1]["busy"]:
            return True
        time.sleep(0.1)
    return False


def last_final():
    return [e for e in request("/api/state?since=0")[1]["events"] if e["kind"] == "final"][-1]


# 1. pure helpers
check("parse_articles reads the matches", [(a["id"], a["distance"]) for a in parse_articles(KB_MESSAGE)] == [("KB-VPN-001", 0.7592), ("KB-VPN-002", 0.8951)])
check("parse_articles: no matches gives an empty list", parse_articles("No relevant knowledge-base information was found.") == [])
check("outcome: successful fix is 'resolved'", outcome_of([{"tool": "restart_vpn", "success": True}]) == "resolved")
check("outcome: failed fix alone is only 'answered'", outcome_of([{"tool": "restart_vpn", "success": False}]) == "answered")
check("outcome: ticket is 'ticket', escalation wins", outcome_of([{"tool": "create_support_ticket", "success": True}]) == "ticket"
      and outcome_of([{"tool": "create_support_ticket", "success": True}, {"tool": "escalate_incident", "success": True}]) == "escalated")

# 2. page and config
code, html = request("/")
check("page is served and talks to the API", code == 200 and "SENTINEL" in html and "/api/state" in html and "http://" not in PAGE.replace("http://127", ""))
check("page has the new features", all(word in PAGE for word in ("Technician", "kbcard", "clearMem", "offBtn", "banner")))
check("page explains live versus offline", "Solid border: a live Gemini run" in PAGE and "Dashed border: the offline workflow" in PAGE)
check("server listens on this computer only", server.server_address[0] == "127.0.0.1")
code, cfg = request("/api/config")
check("config shows model, memory, thoughts and offline mode", cfg == {"model": "stand-in", "memory": True, "thoughts": True, "offline": True}, str(cfg))

# 3. input is validated
check("empty message rejected", request("/api/message", {"text": "  "})[0] == 400)
check("over-long message rejected", request("/api/message", {"text": "x" * 1001})[0] == 400)

# 4. send a message; a second one while busy is refused
code, _ = request("/api/message", {"text": "Username sipho here, the VPN is down."})
code2, _ = request("/api/message", {"text": "another"})
check("message accepted (202); a second one while busy is refused (409)", code == 202 and code2 == 409, f"({code}, {code2})")
check("the run finishes", wait_until_idle())

# 5. the log
state = request("/api/state?since=0")[1]
kinds = [e["kind"] for e in state["events"]]
check("log order: user, thought, action, observation ..., final", kinds[:4] == ["user", "thought", "action", "observation"] and kinds[-1] == "final", str(kinds))
observations = [e for e in state["events"] if e["kind"] == "observation"]
check("observations carry success and seconds from the gateway", all("success" in o and "seconds" in o for o in observations) and observations[2]["success"] is False,
      str([(o["status"], o["success"]) for o in observations]))
check("knowledge search observation carries the matched articles", [a["id"] for a in observations[0].get("articles", [])] == ["KB-VPN-001", "KB-VPN-002"])
final = state["events"][-1]
check("final answer is included", "INC-1001" in final["text"] and "Knowledge base article" in final["text"])
check("live answers are labelled live, with the model name", final.get("mode") == "live" and final.get("model") == "stand-in", str((final.get("mode"), final.get("model"))))
check("final answer: outcome judged from the tools, tool list and time", final["outcome"] == "escalated" and final["tools_used"][0] == "knowledge_search"
      and len(final["tools_used"]) == 5 and final["elapsed"] >= 0.4, f"({final['outcome']}, {final['elapsed']} s)")
check("'since' returns only the new part of the log", len(request(f"/api/state?since={state['total'] - 1}")[1]["events"]) == 1)

# 6. side panels
check("ticket appears with status escalated", [(t["id"], t["status"]) for t in state["tickets"]] == [("INC-1001", "escalated")], str(state["tickets"]))
check("audit log lists the tool calls", [a["tool"] for a in state["audit"]][:2] == ["check_vpn_status", "restart_vpn"], str([a["tool"] for a in state["audit"]]))
code, hist = request("/api/history?username=SIPHO")
check("memory lookup works (case-insensitive)", [e["event"] for e in hist["events"]] == ["escalated", "ticket_created", "fix_failed"], str([e["event"] for e in hist["events"]]))
check("memory lookup for an unknown user is empty", request("/api/history?username=nobody")[1]["events"] == [])

# 7. controls
check("new conversation: accepted and forgets the conversation", request("/api/new", {})[0] == 200 and agent.last_interaction_id is None)
check("reset simulated systems: tickets are cleared", request("/api/reset", {})[0] == 200 and request("/api/state?since=0")[1]["tickets"] == [])

# 8. other outcomes
agent.client = Flow(thabo_flow)
request("/api/message", {"text": "Hi, my username is thabo. My VPN isn't working."})
wait_until_idle()
check("a successful fix is shown as 'resolved'", last_final()["outcome"] == "resolved")
agent.client = Flow([([Step("text")], "Which username should I use?")])
request("/api/message", {"text": "My VPN isn't working."})
wait_until_idle()
check("a reply with no system change is shown as 'answered'", last_final()["outcome"] == "answered" and last_final()["tools_used"] == [])

# 9. clear memory
check("memory has entries before clearing", len(request("/api/history?username=sipho")[1]["events"]) > 0)
check("clear memory: accepted and the history is empty", request("/api/clear-memory", {})[0] == 200 and request("/api/history?username=sipho")[1]["events"] == [])
agent2 = GatewayAgent(client=Flow([]), model="stand-in", memory=None, show_thoughts=False)
server2 = make_server(Console(agent2, None), 0)
threading.Thread(target=server2.serve_forever, daemon=True).start()
BASE2 = f"http://127.0.0.1:{server2.server_address[1]}"
check("clear memory is refused when memory is switched off", request("/api/clear-memory", {}, base=BASE2)[0] == 400 and request("/api/config", base=BASE2)[1]["memory"] is False)
server2.shutdown()

# 10. offline workflow (Asante's scripted workflow), with a stand-in for it
fake = types.ModuleType("app.agent.local_react")
def fake_run(incident_id, return_details=False):
    print("noisy output that must not reach the console")
    return {"incident_id": incident_id, "incident": "Incident ID: INC-1001\nUser: John Smith", "knowledge": "Source: vpn.txt\nChroma distance: 0.54\n\ntext",
            "diagnostic_type": "vpn", "diagnostic": "VPN Diagnostic Result:\n- User authentication: FAILED", "decision": "Authentication has failed.",
            "remediation_action": None, "remediation_observation": None, "update_result": "Incident updated successfully.",
            "escalation_required": True, "escalation": "Incident escalation completed.", "outcome": "Escalated to the Identity and Access Team.", "summary": "Incident Resolution Summary"}
fake.run_local_react = fake_run
sys.modules["app.agent.local_react"] = fake
incidents = request("/api/offline-incidents")[1]
check("offline incidents are listed", [i["id"] for i in incidents] == ["INC-1001", "INC-1002", "INC-1003"], str([i["id"] for i in incidents]))
check("unknown offline incident rejected", request("/api/offline", {"incident": "INC-9"})[0] == 400)
before = request("/api/state?since=0")[1]["total"]
check("offline run accepted", request("/api/offline", {"incident": "INC-1001"})[0] == 202)
check("offline run finishes", wait_until_idle())
offline = request(f"/api/state?since={before}")[1]["events"]
check("offline events: user line, then thought, action, observation ..., final, all tagged offline",
      offline[0]["kind"] == "user" and {"thought", "action", "observation", "final"} <= {e["kind"] for e in offline} and all(e.get("source") == "offline" for e in offline),
      str([e["kind"] for e in offline][:6]))
check("offline answers are labelled offline", offline[-1].get("mode") == "offline")
check("offline final answer: outcome and tools", offline[-1]["outcome"] == "escalated" and "lookup_incident" in offline[-1]["tools_used"] and "escalate_incident" in offline[-1]["tools_used"])
resolved = offline_events({**fake_run("INC-1003"), "escalation_required": False, "escalation": None, "remediation_action": "Restart email client and reconnect",
                           "remediation_observation": "Mail client: RESTARTED", "outcome": "Resolved through simulated local remediation."})
check("offline workflow with a fix is shown as resolved", resolved[-1]["outcome"] == "resolved" and any(e.get("tool") == "Restart email client and reconnect" for e in resolved))

# 11. errors do not kill the server
agent.client = Flow([([Step("text")], "")] * 2)          # always empty: the agent returns a clean message
request("/api/message", {"text": "hello"})
wait_until_idle()
check("an early stop is shown as a message, not as silence",
      any(e["kind"] == "error" and "empty answer" in e["text"] for e in request("/api/state?since=0")[1]["events"]))
check("server still answers after a difficult reply", request("/api/config")[0] == 200)

class Down:
    def __init__(self): self.interactions = self
    def create(self, **kw): raise RuntimeError("Error code: 503 - high demand")
agent.client = Down()
request("/api/message", {"text": "hello again"})
wait_until_idle()
check("Gemini down: the page gets an explanation",
      any(e["kind"] == "error" and "not responding" in e["text"] for e in request("/api/state?since=0")[1]["events"]))
check("unknown path gives 404", request("/nope")[0] == 404)

server.shutdown()
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
