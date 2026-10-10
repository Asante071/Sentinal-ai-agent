"""SentinelAI's local, demo-ready web dashboard.

This module deliberately calls ``run_local_react`` instead of Gemini.  It
keeps the presentation layer independent so a hosted agent can be wired in
later without changing the HTML or API contract.
"""

from __future__ import annotations

import html
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _fields(text: str) -> dict[str, str]:
    """Convert the project's human-readable incident tool output to fields."""
    return {
        key.strip(): value.strip()
        for key, value in re.findall(r"^([^:\n]+):\s*(.+)$", text, re.MULTILINE)
    }


def _escape(value: object) -> str:
    return html.escape(str(value))


def _lines(text: str) -> str:
    return "<br>".join(_escape(line.strip()) for line in text.strip().splitlines() if line.strip())


def build_dashboard(incident_id: str) -> str:
    # Import the local workflow on demand.  It loads the sentence-transformer
    # model used by ChromaDB, so deferring it lets the web server start and
    # display its URL immediately after ``python -m app.dashboard``.
    from app.agent.local_react import run_local_react
    from app.tools.incident_lookup import INCIDENTS

    incident_id = incident_id.upper()
    if incident_id not in INCIDENTS:
        incident_id = "INC-1001"

    result = run_local_react(incident_id, return_details=True)
    incident = _fields(result["incident"])
    source_match = re.search(r"Source:\s*(.+)", result["knowledge"])
    distance_match = re.search(r"Chroma distance:\s*([0-9.]+)", result["knowledge"])
    source = source_match.group(1).strip() if source_match else "No source returned"
    distance = float(distance_match.group(1)) if distance_match else None
    distance_display = f"{distance:.4f}" if distance is not None else "Unavailable"
    status = "ESCALATED" if result["escalation_required"] else "IN PROGRESS"
    status_class = "danger" if result["escalation_required"] else "amber"

    activity = [
        ("01", "Thought · understand incident", "Retrieved the current incident record.", "complete"),
        ("02", "Action · knowledge retrieval", f"Matched {source}; Chroma distance: {distance_display} (lower is closer).", "complete"),
        (
            "03",
            f"Action · {('MANUAL REVIEW' if result['diagnostic_type'] == 'unknown' else result['diagnostic_type'].upper())} diagnostic",
            "Observation · collected technical evidence from the local diagnostic tool."
            if result["diagnostic_type"] != "unknown" else "No automated diagnostic is available until the incident is classified.",
            "complete",
        ),
    ]
    if result["remediation_action"]:
        activity.extend([
            ("04", f"Thought · remediation", result["decision"], "complete"),
            ("05", f"Action · {result['remediation_action']}", "Observation · " + result["remediation_observation"].strip().replace("\n", " "), "complete"),
            ("06", "Decision · outcome", result["outcome"], "active"),
        ])
    else:
        activity.extend([
            ("04", "Decision evaluation", result["decision"], "complete"),
            ("05", "Incident update", "Recorded the investigation notes and current status.", "complete"),
            ("06", "Escalation" if result["escalation_required"] else "Standard handling", result["outcome"], "active"),
        ])
    activity_html = "".join(
        f'''<article class="step {state}"><span class="step-number">{number}</span><div><h3>{_escape(title)}</h3><p>{_escape(detail)}</p></div><span class="check">✓</span></article>'''
        for number, title, detail, state in activity
    )

    diagnostic_html = _lines(result["diagnostic"])
    remediation_html = _lines(result["remediation_observation"] or "No remediation action was required.")
    escalation_html = _lines(result["escalation"] or "No escalation required.")
    summary_html = _lines(result["summary"])
    options_html = "".join(
        f'<option value="{key}" {"selected" if key == incident_id else ""}>{key} — {_escape(value["issue"])}</option>'
        for key, value in INCIDENTS.items()
    )

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SentinelAI | Incident command centre</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#07111f;color:#e9f0fb;font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}} .shell{{max-width:1440px;margin:auto;padding:28px}} header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #223247;padding-bottom:24px}} .brand{{font-weight:800;font-size:25px;letter-spacing:3px}} .brand b{{color:#49dcb1}} .live{{color:#8ff0d0;font-size:12px;letter-spacing:1px}} .live:before{{content:'●';color:#49dcb1;margin-right:8px}} .hero{{display:flex;justify-content:space-between;gap:20px;align-items:end;padding:30px 0 22px}} h1{{font-size:28px;margin:0}} .eyebrow{{color:#7f9ab8;font-size:12px;letter-spacing:1.5px;text-transform:uppercase}} select,button{{border:1px solid #36506d;border-radius:8px;background:#101f33;color:#eef6ff;padding:11px 13px}} button{{cursor:pointer;background:#49dcb1;color:#06231e;font-weight:800;margin-left:7px}} .grid{{display:grid;grid-template-columns:1.2fr .8fr;gap:18px}} .card{{background:#0d1a2c;border:1px solid #1d3047;border-radius:13px;padding:21px;box-shadow:0 12px 30px #0002}} .wide{{grid-column:span 2}} h2{{font-size:13px;letter-spacing:1.2px;color:#91abc7;text-transform:uppercase;margin:0 0 17px}} .incident{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}} .label{{display:block;color:#7893b0;font-size:12px;text-transform:uppercase;letter-spacing:.7px}} .value{{font-size:17px;font-weight:650}} .pill{{display:inline-block;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:800;letter-spacing:.7px}} .danger{{background:#3b1d2b;color:#ff9eb3}} .amber{{background:#382d16;color:#ffd477}} .step{{display:grid;grid-template-columns:1fr 25px;gap:12px;border-left:1px solid #28425d;padding:0 0 20px 17px;margin-left:16px;position:relative}} .step-number{{position:absolute;left:-17px;background:#123246;border:1px solid #3d7a91;border-radius:50%;width:33px;height:33px;text-align:center;line-height:31px;color:#70e6c6;font-size:11px}} .step h3{{margin:0;font-size:15px}} .step p{{color:#a9bdd2;margin:4px 0 0;font-size:13px}} .check{{color:#52e5b8;font-size:19px}} .metric{{background:#0a1728;border-radius:9px;padding:14px;margin-bottom:12px}} .metric strong{{font-size:22px;color:#69ebcb}} .mono{{background:#081421;border:1px solid #20364f;border-radius:8px;padding:15px;color:#c5d5e8;font:13px/1.6 ui-monospace,Consolas,monospace;white-space:normal}} .summary{{border-left:3px solid #49dcb1;padding-left:16px;color:#d8e4f0}} .footer{{color:#728ba5;margin:18px 0 0;font-size:12px}} @media(max-width:780px){{.grid{{grid-template-columns:1fr}}.wide{{grid-column:auto}}.incident{{grid-template-columns:1fr 1fr}}.hero,header{{align-items:flex-start;flex-direction:column}}}}
</style></head><body><main class="shell"><header><div class="brand">SENTINEL<b>AI</b></div><div class="live">LOCAL WORKFLOW ONLINE</div></header>
<section class="hero"><div><div class="eyebrow">Autonomous service desk</div><h1>Incident investigation command centre</h1></div><form method="get"><select name="incident">{options_html}</select><button type="submit">Run investigation</button></form></section>
<section class="grid"><article class="card wide"><h2>Incident details</h2><div class="incident"><div><span class="label">Incident ID</span><span class="value">{_escape(incident.get('Incident ID', incident_id))}</span></div><div><span class="label">Priority</span><span class="value"><span class="pill danger">{_escape(incident.get('Priority','High')).upper()}</span></span></div><div><span class="label">User</span><span class="value">{_escape(incident.get('User','—'))}</span></div><div><span class="label">Issue</span><span class="value">{_escape(incident.get('Issue','—'))}</span></div><div><span class="label">Assigned team</span><span class="value">{_escape(incident.get('Assigned Team','—'))}</span></div><div><span class="label">Current status</span><span class="value"><span class="pill {status_class}">{status}</span></span></div></div></article>
<article class="card"><h2>Agent activity · ReAct trace</h2>{activity_html}</article>
<article class="card"><h2>RAG evidence</h2><div class="metric"><span class="label">Knowledge source</span><strong>{_escape(source)}</strong></div><div class="metric"><span class="label">Chroma distance</span><strong>{distance_display}</strong><span class="label">Lower distance indicates a closer semantic match; it is not a percentage.</span></div><div class="mono">{_lines(result['knowledge'])}</div></article>
<article class="card"><h2>Diagnostic observations</h2><div class="mono">{diagnostic_html}</div></article>
<article class="card"><h2>Remediation observation</h2><div class="mono">{remediation_html}</div></article>
<article class="card"><h2>Escalation status</h2><span class="pill {status_class}">{status}</span><div class="mono" style="margin-top:14px">{escalation_html}</div></article>
<article class="card wide"><h2>Incident resolution summary</h2><div class="summary">{summary_html}</div></article></section><p class="footer">Demo backend: deterministic local ReAct workflow · RAG: ChromaDB knowledge search · Gemini calls: disabled</p></main></body></html>'''


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        params = parse_qs(urlparse(self.path).query)
        page = build_dashboard(params.get("incident", ["INC-1001"])[0])
        encoded = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    print(f"Starting SentinelAI dashboard: http://{host}:{port}", flush=True)
    print("The first investigation loads the local RAG model and may take a moment.", flush=True)
    ThreadingHTTPServer((host, port), DashboardHandler).serve_forever()


if __name__ == "__main__":
    run()
