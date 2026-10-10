"""Scripted scenarios = the path a correct agent should take.
Run: python test_scenarios.py   (prints table + writes test_results.csv)   or: pytest -q
Later, Asanté's agent can be run on the same 'message' fields and its tool sequence compared with 'expected_tools'."""
import csv
import tools

# Each step: (tool, args). 'check' verifies the end state.
SCENARIOS = [
    dict(id="S1", category="VPN", message="Thabo: my VPN isn't working.", outcome="resolved",
         steps=[("check_vpn_status", {"username": "thabo"}), ("restart_vpn", {"username": "thabo"})],
         check=lambda: tools.STATE["users"]["thabo"]["vpn"] == "active"),
    dict(id="S2", category="VPN", message="Sipho: VPN down, restart doesn't help.", outcome="escalated",
         steps=[("check_vpn_status", {"username": "sipho"}), ("restart_vpn", {"username": "sipho"}),
                ("create_support_ticket", {"username": "sipho", "category": "vpn", "summary": "VPN restart failed", "priority": "high"}),
                ("escalate_incident", {"ticket_id": "INC-1001", "reason": "VPN restart failed"})],
         check=lambda: tools.STATE["tickets"]["INC-1001"]["status"] == "escalated"),
    dict(id="S3", category="Account", message="Lerato: I'm locked out.", outcome="resolved",
         steps=[("check_account_status", {"username": "lerato"}), ("reset_password", {"username": "lerato"})],
         check=lambda: tools.STATE["users"]["lerato"]["account"] == "active"),
    dict(id="S4", category="Account", message="Kagiso: reset my password.", outcome="escalated",
         steps=[("check_account_status", {"username": "kagiso"}), ("reset_password", {"username": "kagiso"}),
                ("create_support_ticket", {"username": "kagiso", "category": "account", "summary": "Account disabled", "priority": "medium"}),
                ("escalate_incident", {"ticket_id": "INC-1001", "reason": "Disabled account"})],
         check=lambda: tools.STATE["tickets"]["INC-1001"]["status"] == "escalated"),
    dict(id="S5", category="Email", message="Nomsa: Outlook won't send mail.", outcome="resolved",
         steps=[("check_email_service", {"username": "nomsa"}), ("fix_email_issue", {"username": "nomsa"})],
         check=lambda: tools.STATE["users"]["nomsa"]["mailbox_used_pct"] < 95),
    dict(id="S6", category="Printer", message="Printer PRN-02 has 14 stuck jobs.", outcome="resolved",
         steps=[("check_printer_status", {"printer_id": "PRN-02"}), ("troubleshoot_printer", {"printer_id": "PRN-02"})],
         check=lambda: tools.STATE["printers"]["PRN-02"]["status"] == "online"),
    dict(id="S7", category="Printer", message="Finance printer PRN-03 not printing.", outcome="escalated",
         steps=[("check_printer_status", {"printer_id": "PRN-03"}), ("troubleshoot_printer", {"printer_id": "PRN-03"}),
                ("create_support_ticket", {"username": "thabo", "category": "printer", "summary": "PRN-03 hardware fault", "priority": "medium"}),
                ("escalate_incident", {"ticket_id": "INC-1001", "reason": "Hardware fault"})],
         check=lambda: tools.STATE["tickets"]["INC-1001"]["status"] == "escalated"),
    dict(id="S8", category="Error handling", message="Unknown user 'zanele' asks for VPN help.", outcome="graceful failure",
         steps=[("check_vpn_status", {"username": "zanele"})],
         check=lambda: tools.STATE["audit_log"][-1]["status"] == "USER_NOT_FOUND"),
]

def run_scenario(s):
    tools.reset_state()
    calls, last = [], None
    for name, args in s["steps"]:
        last = tools.execute_tool(name, args)
        calls.append(f"{name}:{'OK' if last['success'] else last['status']}")
        if last["status"] in ("BAD_ARGUMENTS", "UNKNOWN_TOOL"):   # tool wiring bug, not an expected failure
            return False, calls
    return s["check"](), calls

def test_all_scenarios():
    for s in SCENARIOS:
        passed, _ = run_scenario(s)
        assert passed, f"{s['id']} failed"

if __name__ == "__main__":
    rows = []
    for s in SCENARIOS:
        passed, calls = run_scenario(s)
        rows.append({"id": s["id"], "category": s["category"], "message": s["message"], "expected_outcome": s["outcome"],
                     "tool_sequence": " -> ".join(calls), "result": "PASS" if passed else "FAIL"})
    with open("test_results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    for r in rows: print(f"{r['id']} [{r['result']}] {r['category']:<14} {r['tool_sequence']}")
    print(f"\n{sum(r['result']=='PASS' for r in rows)}/{len(rows)} passed -> test_results.csv")
