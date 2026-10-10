"""SentinelAI live console: a web page that shows the REAL Gemini agent at work.

Usage (from the project folder):   python -m app.live_dashboard   then open  http://127.0.0.1:8001

You type a problem; the page shows, as it happens, each THOUGHT (Gemini's reasoning summary), ACTION (the tool and its
arguments) and OBSERVATION (what the tool returned), then the final answer with its knowledge-base article. Beside it:
the tickets in the simulated system, the tool audit log, and what the agent remembers about a user.

It is the project's single dashboard. Asante's scripted local workflow (no AI, three preset incidents) is built in as
an "Offline workflow" mode, so a demo still works when Gemini is down. A Technician / Employee switch shows the full
reasoning or only the conversation. Uses only Python's standard library for the server; serves on 127.0.0.1 only.
"""
import contextlib
import importlib
import io
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

load_dotenv()

from app.agent.gateway_agent import GatewayAgent  # noqa: E402  (this also makes Mmabotse's backend importable)
import tools as backend_tools  # noqa: E402

MAX_TEXT = 1000
FIX_TOOLS = {"restart_vpn", "reset_password", "fix_email_issue", "troubleshoot_printer"}
ARTICLE = re.compile(r"Result (\d+): (\S+) \((.+?)\), distance ([0-9.]+)")


def parse_articles(message):
    """The knowledge-base matches listed in a knowledge_search result."""
    return [{"rank": int(n), "id": i, "file": f, "distance": float(d)} for n, i, f, d in ARTICLE.findall(message or "")]


def outcome_of(observations):
    """What happened, judged from what the tools actually did (not from what the model says)."""
    done = lambda o: o.get("success") is True
    if any(o["tool"] == "escalate_incident" and done(o) for o in observations):
        return "escalated"
    if any(o["tool"] == "create_support_ticket" and done(o) for o in observations):
        return "ticket"
    if any(o["tool"] in FIX_TOOLS and done(o) for o in observations):
        return "resolved"
    return "answered"


def offline_incidents():
    try:
        from app.tools.incident_lookup import INCIDENTS
    except Exception:
        return []
    return [{"id": k, "issue": v.get("issue", ""), "user": v.get("user", "")} for k, v in INCIDENTS.items()]


def offline_events(r):
    """Turn the result of Asante's scripted workflow into timeline events."""
    ev = []

    def add(kind, **kw):
        ev.append({"kind": kind, "source": "offline", **kw})

    def step(thought, tool, args, status, message, ok=True):
        add("thought", text=thought)
        add("action", tool=tool, args=args)
        add("observation", tool=tool, status=status, message=str(message or "").strip(), success=ok)

    iid = r["incident_id"]
    step("I need to understand the incident before deciding what action to take.", "lookup_incident", {"incident_id": iid}, "FOUND", r["incident"])
    step("I should retrieve relevant organisational knowledge for this incident.", "knowledge_search", {"incident": iid}, "FOUND", r["knowledge"])
    kind = r.get("diagnostic_type", "unknown")
    if kind != "unknown":
        step(f"The incident indicates a {kind}-related problem. I should run the {kind} diagnostic.", "run_diagnostic", {"type": kind}, "DIAGNOSTIC", r["diagnostic"])
    else:
        add("thought", text="The incident does not match an available diagnostic category. It requires manual service-desk classification.")
    add("thought", text=r.get("decision", ""))
    if r.get("remediation_action"):
        add("action", tool=r["remediation_action"], args={"incident_id": iid})
        add("observation", tool=r["remediation_action"], status="REMEDIATED", message=str(r.get("remediation_observation") or "").strip(), success=True)
    add("action", tool="update_incident", args={"incident_id": iid, "status": "In Progress"})
    add("observation", tool="update_incident", status="UPDATED", message=str(r.get("update_result") or "").strip(), success=True)
    if r.get("escalation_required"):
        add("action", tool="escalate_incident", args={"incident_id": iid})
        add("observation", tool="escalate_incident", status="ESCALATED", message=str(r.get("escalation") or "").strip(), success=True)
    add("action", tool="generate_incident_summary", args={"incident_id": iid})
    add("observation", tool="generate_incident_summary", status="SUMMARY", message=str(r.get("summary") or "").strip(), success=True)
    outcome = "escalated" if r.get("escalation_required") else ("resolved" if r.get("remediation_action") else "answered")
    add("final", text=r.get("outcome", ""), outcome=outcome, warnings=[],
        tools_used=[e["tool"] for e in ev if e["kind"] == "observation"])
    return ev


class Console:
    """Runs the agent in the background and keeps one growing log of everything that happened."""

    def __init__(self, agent, memory=None):
        self.agent, self.memory = agent, memory
        self.log, self.busy = [], False
        self._lock = threading.Lock()
        self._sync_lock = threading.Lock()
        self._ref, self._synced, self._obs = None, 0, 0
        self._run_obs, self._t0 = [], 0.0

    # ---- talking to the agent ----
    def post(self, text):
        with self._lock:
            if self.busy:
                return False
            self.busy = True
            self._t0 = time.time()
            self.log.append({"kind": "user", "text": text})
        threading.Thread(target=self._work, args=(text,), daemon=True).start()
        return True

    def _work(self, text):
        try:
            reply = self.agent.run(text, verbose=False)
            self.sync()
            if not any(e.get("kind") == "final" for e in self.agent.events):
                # the agent stopped early (for example Gemini did not answer): say so instead of showing nothing
                self.log.append({"kind": "error", "text": reply or "The agent returned no answer."})
        except Exception as error:
            self.log.append({"kind": "error", "text": f"{type(error).__name__}: {error}"})
        finally:
            self.sync()
            self.busy = False

    def post_offline(self, incident_id):
        with self._lock:
            if self.busy:
                return False
            self.busy = True
            self.log.append({"kind": "user", "text": f"Run the offline workflow on {incident_id}", "source": "offline"})
        threading.Thread(target=self._work_offline, args=(incident_id,), daemon=True).start()
        return True

    def _work_offline(self, incident_id):
        started = time.time()
        try:
            run = importlib.import_module("app.agent.local_react").run_local_react   # loaded on first use (it is heavy)
            with contextlib.redirect_stdout(io.StringIO()):
                result = run(incident_id, return_details=True)
            events = offline_events(result)
            events[-1]["elapsed"] = round(time.time() - started, 1)
            self.log.extend(events)
        except Exception as error:
            self.log.append({"kind": "error", "text": f"The offline workflow failed: {type(error).__name__}: {error}"})
        finally:
            self.busy = False

    def sync(self):
        """Copy new events from the agent into the log, adding what the gateway knows (success, seconds)
        and, on the final answer, the outcome judged from what the tools did."""
        with self._sync_lock:
            events = self.agent.events
            if events is not self._ref:               # a new run() started: its list is a new object
                self._ref, self._synced, self._run_obs = events, 0, []
            new = list(events[self._synced:])
            self._synced += len(new)
            for event in new:
                if event.get("kind") == "user":
                    continue                           # already logged when the message was posted
                event = dict(event)
                if event["kind"] == "observation":
                    steps = self.agent.gateway.steps
                    if self._obs < len(steps):
                        event["success"], event["seconds"] = steps[self._obs]["success"], steps[self._obs]["seconds"]
                    self._obs += 1
                    if event.get("tool") == "knowledge_search":
                        event["articles"] = parse_articles(event.get("message"))
                    self._run_obs.append({"tool": event.get("tool"), "success": event.get("success")})
                elif event["kind"] == "final":
                    event["warnings"] = list(self.agent.warnings)
                    event["outcome"] = outcome_of(self._run_obs)
                    event["tools_used"] = [o["tool"] for o in self._run_obs]
                    event["elapsed"] = round(time.time() - self._t0, 1)
                self.log.append(event)

    def new_conversation(self):
        self.agent.new_conversation()
        self.log.append({"kind": "system", "text": "New conversation started. Long-term memory is kept."})

    def clear_memory(self):
        self.memory.clear()
        self.log.append({"kind": "system", "text": "The agent's memory of past problems was cleared."})

    def reset_systems(self):
        backend_tools.reset_state()
        self.log.append({"kind": "system", "text": "Simulated systems reset (users, printers and tickets are back to the start)."})

    # ---- what the page asks for ----
    def state(self, since):
        self.sync()
        return {"events": self.log[since:], "total": len(self.log), "busy": self.busy,
                "tickets": [dict(t) for t in backend_tools.STATE["tickets"].values()],
                "audit": list(backend_tools.STATE["audit_log"][-15:])}

    def config(self):
        return {"model": self.agent.model, "memory": self.memory is not None, "thoughts": bool(self.agent.show_thoughts),
                "offline": bool(offline_incidents())}

    def history(self, username):
        return self.memory.history(username, limit=10) if self.memory is not None else []


def make_handler(console):
    class Handler(BaseHTTPRequestHandler):
        server_version = "SentinelConsole/1.0"

        def log_message(self, *args):
            pass

        def _send(self, code, body, content_type="application/json; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, default=str))

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if url.path == "/":
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif url.path == "/api/config":
                self._json(200, console.config())
            elif url.path == "/api/state":
                try:
                    since = max(0, int(query.get("since", ["0"])[0]))
                except ValueError:
                    since = 0
                self._json(200, console.state(since))
            elif url.path == "/api/offline-incidents":
                self._json(200, offline_incidents())
            elif url.path == "/api/history":
                username = (query.get("username", [""])[0] or "").strip().lower()[:40]
                self._json(200, {"username": username, "events": console.history(username) if username else []})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 20000)
                payload = json.loads(self.rfile.read(length) or b"{}")
            except Exception:
                return self._json(400, {"error": "invalid request"})
            if url.path == "/api/message":
                text = str(payload.get("text", "")).strip()
                if not text:
                    return self._json(400, {"error": "Type a message first."})
                if len(text) > MAX_TEXT:
                    return self._json(400, {"error": f"Message too long (max {MAX_TEXT} characters)."})
                if not console.post(text):
                    return self._json(409, {"error": "The agent is still working on the previous message."})
                self._json(202, {"ok": True})
            elif url.path == "/api/offline":
                incident = str(payload.get("incident", "")).strip().upper()
                if incident not in [i["id"] for i in offline_incidents()]:
                    return self._json(400, {"error": "Unknown incident."})
                if not console.post_offline(incident):
                    return self._json(409, {"error": "The agent is busy."})
                self._json(202, {"ok": True})
            elif url.path == "/api/clear-memory":
                if console.memory is None:
                    return self._json(400, {"error": "Memory is switched off."})
                if console.busy:
                    return self._json(409, {"error": "The agent is busy."})
                console.clear_memory()
                self._json(200, {"ok": True})
            elif url.path in ("/api/new", "/api/reset"):
                if console.busy:
                    return self._json(409, {"error": "The agent is busy."})
                (console.new_conversation if url.path == "/api/new" else console.reset_systems)()
                self._json(200, {"ok": True})
            else:
                self._json(404, {"error": "not found"})

    return Handler


def make_server(console, port=8001):
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(console))


def main():
    port = int(os.getenv("CONSOLE_PORT", "8001"))
    memory = None
    if "--no-memory" not in sys.argv:
        from app.agent.memory_store import MemoryStore
        memory = MemoryStore()
    print("Starting the agent (the first start loads the knowledge base and can take 10 to 30 seconds)...")
    agent = GatewayAgent(memory=memory)
    console = Console(agent, memory)
    server = make_server(console, port)
    print(f"Model: {agent.model}   Memory: {'ON' if memory else 'OFF'}   Thoughts: {'ON' if agent.show_thoughts else 'OFF'}")
    print(f"Open http://127.0.0.1:{port} in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SentinelAI live console</title>
<style>
:root{--bg:#0b1220;--panel:#111a2c;--line:#1f2d47;--text:#e6edf7;--muted:#8fa1bd;--accent:#3ddbb0;--blue:#6aa9ff;--violet:#b79cff;--red:#ff7a7a;--amber:#f5c26b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 "Segoe UI",-apple-system,Roboto,Helvetica,Arial,sans-serif}
header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:14px 22px;border-bottom:1px solid var(--line)}
.logo{font-weight:800;letter-spacing:.14em;font-size:20px}.logo b{color:var(--accent)}.logo small{letter-spacing:0;font-weight:500;font-size:14px;color:var(--muted);margin-left:8px}
.chips{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.chip{border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:12px;color:var(--muted)}
.chip.on{color:var(--accent);border-color:#235a4b}
.grid{display:grid;grid-template-columns:320px minmax(0,1fr) 340px;gap:16px;padding:16px 22px}
@media(max-width:1150px){.grid{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px}
h2{margin:0 0 10px;font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
textarea,input[type=text],select{width:100%;background:#0c1527;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit}
textarea{min-height:90px;resize:vertical}
button{background:var(--accent);color:#06251d;border:0;border-radius:10px;padding:9px 14px;font:inherit;font-weight:700;cursor:pointer}
button.ghost{background:transparent;color:var(--text);border:1px solid var(--line);font-weight:600}
button.small{padding:5px 12px;font-size:13px}
button:disabled{opacity:.5;cursor:not-allowed}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.status{margin-top:10px;font-size:13px;color:var(--muted)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--accent);margin-right:6px}
.dot.busy{background:var(--amber);animation:pulse 1s infinite}
@keyframes pulse{50%{opacity:.25}}
.examples button{display:block;width:100%;text-align:left;margin-top:6px;background:#0c1527;color:var(--text);border:1px solid var(--line);font-weight:500;font-size:13px}
#timeline{display:flex;flex-direction:column;gap:10px;max-height:calc(100vh - 140px);min-height:300px;overflow:auto;padding-right:4px}
.ev{border:1px solid var(--line);border-radius:12px;padding:10px 12px;background:#0e1830}
.ev.offline{border-style:dashed}
.tag{font-size:11px;letter-spacing:.12em;font-weight:700;margin-bottom:4px}
.tag .src{color:var(--muted);font-weight:600;margin-left:6px}
.user{align-self:flex-end;max-width:85%;background:#15335a;border-color:#27518a}
.thought{border-left:3px solid var(--violet)}.thought .tag{color:var(--violet)}.thought .body{color:#c9bff2;font-style:italic}
.action{border-left:3px solid var(--blue)}.action .tag{color:var(--blue)}
.obs{border-left:3px solid var(--accent)}.obs .tag{color:var(--accent)}
.obs.bad{border-left-color:var(--red)}.obs.bad .tag{color:var(--red)}
.final{border:1px solid #235a4b;background:#0d2230}.final .tag{color:var(--accent)}
.sys{text-align:center;color:var(--muted);font-size:13px;border:0;background:none}
.pre{white-space:pre-wrap}
code,.mono{font-family:Consolas,Menlo,monospace;font-size:13px;color:#cfe0ff;word-break:break-word}
.mono.pre{white-space:pre-wrap}
.clamp{display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.more{background:none;color:var(--violet);border:0;padding:0;margin-top:4px;font-size:12px;cursor:pointer;font-weight:600}
.pill{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:700;margin-right:6px}
.pill.good{background:#12392f;color:var(--accent)}.pill.bad{background:#3b1a1f;color:var(--red)}.pill.neutral{background:#1c2b47;color:var(--muted)}.pill.amber{background:#3d3015;color:var(--amber)}
.banner{display:flex;gap:8px;align-items:center;margin-bottom:8px}.banner .pill{font-size:13px;padding:2px 12px}
.source{margin-top:8px;font-size:13px;color:var(--muted)}
.stats{margin-top:6px;font-size:12px;color:var(--muted)}
.warn{margin-top:8px;color:var(--amber);font-size:13px}
.kb{display:flex;flex-direction:column;gap:6px;margin-top:6px}
.kbcard{border:1px solid var(--line);border-radius:10px;padding:7px 10px;background:#0b1428}
.kbcard.top{border-color:#235a4b}
.kbcard .t{font-size:13px}.kbcard .t b{color:var(--text)}.kbcard .t span{color:var(--muted);margin-left:6px;font-size:12px}
.bar{height:6px;border-radius:4px;background:#1c2b47;margin-top:5px;overflow:hidden}
.fill{height:100%;background:var(--accent)}
.kbcard .d{font-size:12px;color:var(--muted);margin-top:3px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:5px 4px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:11px;letter-spacing:.08em;text-transform:uppercase}
.muted{color:var(--muted)}
footer{padding:4px 22px 22px;color:var(--muted);font-size:12px}
body.employee .tech{display:none !important}
</style>
</head>
<body>
<header>
  <div class="logo">SENTINEL<b>AI</b><small>live agent console</small></div>
  <div class="chips">
    <span class="chip" id="chipModel">model</span><span class="chip" id="chipMem">memory</span><span class="chip" id="chipTh">thoughts</span>
    <button class="ghost small" id="viewBtn">View: Technician</button>
  </div>
</header>
<div class="grid">
  <section class="panel">
    <h2>Talk to the agent</h2>
    <textarea id="msg" placeholder="Describe an IT problem, for example: Hi, my username is thabo. My VPN isn't working."></textarea>
    <div class="row"><button id="send">Send</button><button class="ghost" id="newConv">New conversation</button></div>
    <div class="status"><span class="dot" id="dot"></span><span id="statusText">Ready</span></div>
    <h2 style="margin-top:18px">Try these</h2>
    <div class="examples" id="examples"></div>
    <div class="row"><button class="ghost" id="resetSys">Reset simulated systems</button><button class="ghost" id="clearMem">Clear agent memory</button></div>
    <p class="muted" style="font-size:12px">The IT environment is simulated (mock users, printers and tickets). Reset puts it back to the start. Clearing memory makes the agent forget past problems.</p>
    <div id="offPanel" class="tech" style="margin-top:14px;border-top:1px solid var(--line);padding-top:12px">
      <h2>Offline workflow (scripted, no AI)</h2>
      <select id="offSel"></select>
      <div class="row"><button class="ghost" id="offBtn">Run offline workflow</button></div>
      <p class="muted" style="font-size:12px">Asante's original scripted workflow, kept as a backup that works without Gemini. It follows fixed rules, so it gives the same result every time.</p>
    </div>
  </section>
  <section class="panel">
    <h2>Agent activity: thought, action, observation</h2>
    <div id="timeline"></div>
  </section>
  <aside style="display:flex;flex-direction:column;gap:16px">
    <div class="panel"><h2>Tickets</h2><div id="tickets" class="muted">No tickets yet.</div></div>
    <div class="panel tech"><h2>Tool audit log</h2><div id="audit" class="muted">Nothing yet.</div></div>
    <div class="panel tech"><h2>What the agent remembers</h2>
      <div class="row" style="margin-top:0"><input type="text" id="hUser" placeholder="username, e.g. sipho"><button class="ghost" id="hBtn">Look up</button></div>
      <div id="hist" class="muted" style="margin-top:8px">Memory keeps fixes, failed fixes, tickets and escalations for each user.</div>
    </div>
  </aside>
</div>
<footer>Thoughts are summaries of the model's reasoning, shown when Gemini returns one. Observations are the real results of the tools. The Employee view hides the technical detail.</footer>
<script>
const $ = id => document.getElementById(id);
const EXAMPLES = [
  "Hi, my username is thabo. My VPN isn't working.",
  "Username sipho here, the VPN is down and I can't reach the file server.",
  "I'm thabo. The Finance printer PRN-03 is showing an error and won't print.",
  "Username nomsa. Outlook won't send my mail, it says the mailbox is full.",
  "My username is lerato and I'm locked out of my account.",
  "My VPN isn't working.",
  "Can you order me a new laptop and a second monitor?",
  "Username sipho. My VPN is down again."
];
const OUTCOMES = { resolved: ['Resolved', 'good'], escalated: ['Escalated', 'bad'], ticket: ['Ticket opened', 'amber'], answered: ['Answered, no system change', 'neutral'] };
let total = 0, busy = false, timer = null;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function clean(t) { return String(t || '').replace(/\*\*/g, '').replace(/`/g, ''); }
function cleanMd(t) { return clean(t).replace(/^#+\s*/gm, '').replace(/\n{3,}/g, '\n\n').trim(); }
function rich(container, text) {          // **bold** without ever inserting HTML
  String(text || '').split(/\*\*(.+?)\*\*/g).forEach((part, i) => {
    if (!part) return;
    container.appendChild(i % 2 ? el('b', '', part) : document.createTextNode(part));
  });
}
function tagLine(label, ev) {
  const t = el('div', 'tag', label);
  if (ev.source === 'offline') t.appendChild(el('span', 'src', 'offline workflow, no AI'));
  return t;
}
function addEvent(ev) {
  const tl = $('timeline');
  const off = ev.source === 'offline' ? ' offline' : '';
  let node;
  if (ev.kind === 'user' && ev.source === 'offline') {
    node = el('div', 'ev sys', ev.text);
  } else if (ev.kind === 'user') {
    node = el('div', 'ev user');
    node.appendChild(el('div', 'tag', 'YOU'));
    node.appendChild(el('div', 'pre', ev.text));
  } else if (ev.kind === 'thought') {
    node = el('div', 'ev thought tech' + off);
    node.appendChild(tagLine('THOUGHT', ev));
    const body = el('div', 'body clamp', clean(ev.text));
    node.appendChild(body);
    if (clean(ev.text).length > 260) {
      const more = el('button', 'more', 'Show more');
      more.onclick = () => { const c = body.classList.toggle('clamp'); more.textContent = c ? 'Show more' : 'Show less'; };
      node.appendChild(more);
    }
  } else if (ev.kind === 'action') {
    node = el('div', 'ev action tech' + off);
    node.appendChild(tagLine('ACTION', ev));
    const body = el('div', 'body');
    body.appendChild(el('b', '', ev.tool + ' '));
    body.appendChild(el('code', '', JSON.stringify(ev.args)));
    node.appendChild(body);
  } else if (ev.kind === 'observation') {
    const bad = ev.success === false;
    node = el('div', 'ev obs tech' + (bad ? ' bad' : '') + off);
    node.appendChild(tagLine('OBSERVATION', ev));
    const head = el('div', 'body');
    head.appendChild(el('span', 'pill ' + (bad ? 'bad' : 'good'), ev.status || ''));
    if (ev.seconds !== undefined) head.appendChild(el('span', 'muted', ev.seconds + ' s'));
    node.appendChild(head);
    const text = cleanMd(ev.message).slice(0, 700);
    if (ev.articles && ev.articles.length) {
      const box = el('div', 'kb');
      ev.articles.forEach((a, i) => {
        const card = el('div', 'kbcard' + (i === 0 ? ' top' : ''));
        const t = el('div', 't');
        t.appendChild(el('b', '', a.id));
        t.appendChild(el('span', '', a.file));
        card.appendChild(t);
        const bar = el('div', 'bar');
        const fill = el('div', 'fill');
        fill.style.width = Math.max(5, Math.min(100, Math.round((1 - a.distance / 2) * 100))) + '%';
        bar.appendChild(fill);
        card.appendChild(bar);
        card.appendChild(el('div', 'd', 'distance ' + a.distance.toFixed(3) + ' (lower is closer)'));
        box.appendChild(card);
      });
      node.appendChild(box);
      const raw = el('div', 'mono pre', text);
      raw.style.display = 'none';
      const more = el('button', 'more', 'Show article text');
      more.onclick = () => { const hidden = raw.style.display === 'none'; raw.style.display = hidden ? 'block' : 'none'; more.textContent = hidden ? 'Hide article text' : 'Show article text'; };
      node.appendChild(more);
      node.appendChild(raw);
    } else {
      node.appendChild(el('div', 'mono pre', text));
    }
  } else if (ev.kind === 'final') {
    node = el('div', 'ev final' + off);
    node.appendChild(tagLine('FINAL ANSWER', ev));
    if (ev.outcome && OUTCOMES[ev.outcome]) {
      const banner = el('div', 'banner');
      banner.appendChild(el('span', 'pill ' + OUTCOMES[ev.outcome][1], OUTCOMES[ev.outcome][0]));
      node.appendChild(banner);
    }
    const lines = String(ev.text || '').split('\n');
    const body = el('div', 'pre');
    const sources = [];
    const rest = [];
    lines.forEach(l => (/^(Knowledge base article:|Closest knowledge base match:)/i.test(l.trim()) ? sources : rest).push(l));
    rich(body, rest.join('\n').trim());
    node.appendChild(body);
    sources.forEach(s => node.appendChild(el('div', 'source tech', s.trim())));
    (ev.warnings || []).forEach(w => node.appendChild(el('div', 'warn tech', 'Check: ' + w)));
    if (ev.tools_used) {
      const n = ev.tools_used.length;
      node.appendChild(el('div', 'stats tech', n + (n === 1 ? ' tool call' : ' tool calls') + (ev.elapsed !== undefined ? ' · ' + ev.elapsed + ' s' : '')));
    }
  } else {
    node = el('div', 'ev sys', ev.text || '');
    if (ev.kind === 'error') node.style.color = 'var(--red)';
  }
  tl.appendChild(node);
  tl.scrollTop = tl.scrollHeight;
}
function renderTickets(list) {
  const box = $('tickets');
  box.textContent = '';
  if (!list.length) { box.textContent = 'No tickets yet.'; return; }
  const t = el('table');
  const head = el('tr');
  ['ID', 'User', 'Type', 'Status'].forEach(h => head.appendChild(el('th', '', h)));
  t.appendChild(head);
  list.forEach(k => {
    const r = el('tr');
    r.appendChild(el('td', 'mono', k.id));
    r.appendChild(el('td', '', k.user));
    r.appendChild(el('td', '', k.category));
    const s = el('td');
    s.appendChild(el('span', 'pill ' + (k.status === 'escalated' ? 'bad' : 'neutral'), k.status));
    r.appendChild(s);
    t.appendChild(r);
  });
  box.appendChild(t);
}
function renderAudit(list) {
  const box = $('audit');
  box.textContent = '';
  if (!list.length) { box.textContent = 'Nothing yet.'; return; }
  const t = el('table');
  const head = el('tr');
  ['Time', 'Tool', 'Result'].forEach(h => head.appendChild(el('th', '', h)));
  t.appendChild(head);
  list.slice().reverse().forEach(a => {
    const r = el('tr');
    r.appendChild(el('td', 'muted', String(a.time || '').slice(11)));
    r.appendChild(el('td', 'mono', a.tool));
    const s = el('td');
    s.appendChild(el('span', 'pill ' + (a.success ? 'good' : 'bad'), a.status));
    r.appendChild(s);
    t.appendChild(r);
  });
  box.appendChild(t);
}
function setBusy(b) {
  busy = b;
  $('dot').className = 'dot' + (b ? ' busy' : '');
  $('statusText').textContent = b ? 'The agent is working...' : 'Ready';
  ['send', 'newConv', 'resetSys', 'clearMem', 'offBtn'].forEach(id => { $(id).disabled = b; });
}
async function poll() {
  try {
    const r = await fetch('/api/state?since=' + total);
    const s = await r.json();
    s.events.forEach(addEvent);
    total = s.total;
    setBusy(s.busy);
    renderTickets(s.tickets);
    renderAudit(s.audit);
  } catch (e) {
    $('statusText').textContent = 'Cannot reach the console server.';
  }
  timer = setTimeout(poll, busy ? 600 : 2000);
}
async function post(path, body) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  let data = {};
  try { data = await r.json(); } catch (e) {}
  return { ok: r.ok, data };
}
async function send(text) {
  text = (text || '').trim();
  if (!text || busy) return;
  const res = await post('/api/message', { text });
  if (!res.ok) { $('statusText').textContent = res.data.error || 'Message rejected.'; return; }
  $('msg').value = '';
  setBusy(true);
  clearTimeout(timer);
  poll();
}
async function lookup() {
  const u = $('hUser').value.trim();
  const box = $('hist');
  if (!u) return;
  const r = await fetch('/api/history?username=' + encodeURIComponent(u));
  const d = await r.json();
  box.textContent = '';
  if (!d.events.length) { box.textContent = 'Nothing recorded for ' + d.username + '.'; return; }
  const t = el('table');
  d.events.forEach(e => {
    const row = el('tr');
    row.appendChild(el('td', 'muted', String(e.ts || '').replace('T', ' ')));
    row.appendChild(el('td', '', (e.category || '-') + ' / ' + e.event));
    t.appendChild(row);
  });
  box.appendChild(t);
}
async function loadOffline() {
  try {
    const r = await fetch('/api/offline-incidents');
    const list = await r.json();
    list.forEach(i => { const o = el('option', '', i.id + ': ' + i.issue); o.value = i.id; $('offSel').appendChild(o); });
    if (!list.length) $('offPanel').style.display = 'none';
  } catch (e) { $('offPanel').style.display = 'none'; }
}
EXAMPLES.forEach(text => {
  const b = el('button', '', text);
  b.onclick = () => send(text);
  $('examples').appendChild(b);
});
$('send').onclick = () => send($('msg').value);
$('msg').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send($('msg').value); });
$('newConv').onclick = async () => { const r = await post('/api/new'); if (!r.ok) $('statusText').textContent = r.data.error || ''; };
$('resetSys').onclick = async () => { const r = await post('/api/reset'); if (!r.ok) $('statusText').textContent = r.data.error || ''; };
$('clearMem').onclick = async () => {
  if (!confirm("Clear everything the agent remembers about past problems?")) return;
  const r = await post('/api/clear-memory');
  if (!r.ok) $('statusText').textContent = r.data.error || '';
};
$('offBtn').onclick = async () => {
  const id = $('offSel').value;
  if (!id || busy) return;
  const r = await post('/api/offline', { incident: id });
  if (!r.ok) { $('statusText').textContent = r.data.error || ''; return; }
  setBusy(true); clearTimeout(timer); poll();
};
$('viewBtn').onclick = () => {
  const employee = document.body.classList.toggle('employee');
  $('viewBtn').textContent = 'View: ' + (employee ? 'Employee' : 'Technician');
};
$('hBtn').onclick = lookup;
$('hUser').addEventListener('keydown', e => { if (e.key === 'Enter') lookup(); });
fetch('/api/config').then(r => r.json()).then(c => {
  $('chipModel').textContent = c.model;
  $('chipMem').textContent = 'memory ' + (c.memory ? 'on' : 'off'); $('chipMem').className = 'chip' + (c.memory ? ' on' : '');
  $('chipTh').textContent = 'thoughts ' + (c.thoughts ? 'on' : 'off'); $('chipTh').className = 'chip' + (c.thoughts ? ' on' : '');
});
loadOffline();
poll();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
