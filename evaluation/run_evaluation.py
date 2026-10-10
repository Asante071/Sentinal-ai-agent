"""Run the evaluation.  Usage:
    python run_evaluation.py                              # baseline agent
    python run_evaluation.py --agent my_agent:run --name gemini_react    # Asanté's agent (module:function)
Agent signature:  run(message: str, call_tool) -> str
    call_tool(name, args) executes a backend tool and returns its result dict. ALWAYS use it, so calls are logged."""
import argparse, importlib, json, sys, time, csv, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
import tools
from scenarios import SCENARIOS

def in_order(required, calls):
    i = 0
    for c in calls:
        if i < len(required) and c == required[i]: i += 1
    return i == len(required)

def run(agent, name):
    rows = []
    for s in SCENARIOS:
        tools.reset_state(); trace = []
        def call_tool(tool, args=None):
            r = tools.execute_tool(tool, args or {}); trace.append((tool, r["status"])); return r
        t0 = time.time()
        try: answer = agent(s["message"], call_tool) or ""; err = ""
        except Exception as e: answer, err = "", repr(e)
        lat = round(time.time() - t0, 2)
        names = [t for t, _ in trace]
        sel_ok = in_order(s["required"], names) and not (set(names) & set(s["forbidden"]))
        out_ok = bool(s["outcome"](tools.STATE))
        ans_ok = (s.get("answer_has", "").lower() in answer.lower()) if s.get("answer_has") else True
        escalated = any(t["status"] == "escalated" for t in tools.STATE["tickets"].values())
        rows.append(dict(id=s["id"], type=s["type"], message=s["message"], tools_called=" > ".join(names) or "(none)",
                         tool_selection=int(sel_ok), outcome=int(out_ok), answer_check=int(ans_ok),
                         passed=int(sel_ok and out_ok and ans_ok and not err), escalated=int(escalated), expects_escalation=int(s["expects_escalation"]),
                         n_calls=len(names), min_calls=max(len(s["required"]), 0), wiring_errors=sum(st in ("BAD_ARGUMENTS", "UNKNOWN_TOOL") for _, st in trace),
                         latency_s=lat, error=err, final_answer=answer))
    n = len(rows); esc = [r for r in rows if r["expects_escalation"]]
    summary = dict(agent=name, scenarios=n, pass_rate=round(sum(r["passed"] for r in rows) / n * 100, 1),
                   tool_selection_accuracy=round(sum(r["tool_selection"] for r in rows) / n * 100, 1),
                   task_success_rate=round(sum(r["outcome"] for r in rows) / n * 100, 1),
                   correct_escalation_rate=round(sum(r["escalated"] for r in esc) / len(esc) * 100, 1),
                   false_escalation_count=sum(r["escalated"] and not r["expects_escalation"] for r in rows),
                   avg_tool_calls=round(sum(r["n_calls"] for r in rows) / n, 2), wiring_errors=sum(r["wiring_errors"] for r in rows),
                   avg_latency_s=round(sum(r["latency_s"] for r in rows) / n, 2),
                   by_type={t: f"{sum(r['passed'] for r in rows if r['type']==t)}/{sum(1 for r in rows if r['type']==t)}" for t in dict.fromkeys(r["type"] for r in rows)})
    return rows, summary

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--agent", default="baseline_agent:baseline_agent"); ap.add_argument("--name", default="baseline_rule_based")
    a = ap.parse_args(); mod, fn = a.agent.split(":")
    sys.path.insert(0, os.getcwd())
    agent = getattr(importlib.import_module(mod), fn)
    rows, summ = run(agent, a.name)
    os.makedirs("results", exist_ok=True)
    with open(f"results/{a.name}_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    json.dump(summ, open(f"results/{a.name}_summary.json", "w"), indent=2)
    for r in rows: print(f"{r['id']} {'PASS' if r['passed'] else 'FAIL'} [{r['type']:<14}] {r['tools_called']}")
    print(json.dumps(summ, indent=2))
