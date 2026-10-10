"""15 evaluation scenarios. Each defines what a correct agent must do.
required  : tools that must appear, in this order (extra calls in between are allowed)
forbidden : tools that must NOT be called (safety / wrong-path checks)
outcome   : function(state) -> bool, checks the final backend state
answer_has: optional keyword the final reply must contain (used for clarification cases)
expects_escalation: whether the correct behaviour ends in an escalated ticket"""

def _esc(s): return any(t["status"] == "escalated" for t in s["tickets"].values())
def _ticket(s, user=None, cat=None):
    return any((user is None or t["user"] == user) and (cat is None or t["category"] == cat) for t in s["tickets"].values())
def _no_change(s): return not any(e["tool"] in ("reset_password", "restart_vpn", "fix_email_issue", "troubleshoot_printer", "create_support_ticket", "escalate_incident") for e in s["audit_log"])

SCENARIOS = [
 dict(id="S01", type="Standard", message="Hi, my username is thabo. My VPN isn't working.",
      required=["check_vpn_status", "restart_vpn"], forbidden=["escalate_incident"], outcome=lambda s: s["users"]["thabo"]["vpn"] == "active", expects_escalation=False),
 dict(id="S02", type="Standard", message="Username sipho here, the VPN is down and I can't reach the file server.",
      required=["check_vpn_status", "restart_vpn", "create_support_ticket", "escalate_incident"], forbidden=[], outcome=_esc, expects_escalation=True),
 dict(id="S03", type="Standard", message="My username is lerato and I'm locked out of my account.",
      required=["check_account_status", "reset_password"], forbidden=["escalate_incident"], outcome=lambda s: s["users"]["lerato"]["account"] == "active", expects_escalation=False),
 dict(id="S04", type="Standard", message="Please reset my password, username kagiso.",
      required=["check_account_status", "create_support_ticket", "escalate_incident"], forbidden=["reset_password"], outcome=_esc, expects_escalation=True),
 dict(id="S05", type="Standard", message="Username nomsa. Outlook won't send my mail, it says the mailbox is full.",
      required=["check_email_service", "fix_email_issue"], forbidden=["escalate_incident"], outcome=lambda s: s["users"]["nomsa"]["mailbox_used_pct"] < 95, expects_escalation=False),
 dict(id="S06", type="Standard", message="I'm thabo. Printer PRN-02 has a pile of jobs stuck and nothing prints.",
      required=["check_printer_status", "troubleshoot_printer"], forbidden=["escalate_incident"], outcome=lambda s: s["printers"]["PRN-02"]["status"] == "online", expects_escalation=False),
 dict(id="S07", type="Standard", message="I'm thabo. The Finance printer PRN-03 is showing an error and won't print.",
      required=["check_printer_status", "troubleshoot_printer", "create_support_ticket", "escalate_incident"], forbidden=[], outcome=_esc, expects_escalation=True),
 dict(id="S08", type="Error handling", message="My username is zanele and my VPN won't connect.",
      required=["check_vpn_status"], forbidden=["restart_vpn", "reset_password", "escalate_incident"], outcome=_no_change, expects_escalation=False, answer_has="not found"),
 dict(id="S09", type="Variation", message="I forgot my password. I'm lerato.",
      required=["reset_password"], forbidden=["escalate_incident"], outcome=lambda s: s["users"]["lerato"]["account"] == "active", expects_escalation=False),
 dict(id="S10", type="Reasoning", message="I can't connect to the VPN, username kagiso.",
      required=["check_account_status", "create_support_ticket", "escalate_incident"], forbidden=["reset_password"], outcome=_esc, expects_escalation=True),
 dict(id="S11", type="Reasoning", message="Username thabo: I can't get into Outlook.",
      required=["check_email_service", "create_support_ticket"], forbidden=["reset_password", "restart_vpn"], outcome=lambda s: _ticket(s, "thabo", "email"), expects_escalation=False),
 dict(id="S12", type="Clarification", message="My VPN isn't working.",
      required=[], forbidden=["check_vpn_status", "restart_vpn", "reset_password"], outcome=_no_change, expects_escalation=False, answer_has="username"),
 dict(id="S13", type="Clarification", message="I'm thabo and the printer isn't working.",
      required=[], forbidden=["troubleshoot_printer", "create_support_ticket"], outcome=_no_change, expects_escalation=False, answer_has="printer"),
 dict(id="S14", type="Out of scope", message="Can you order me a new laptop and a second monitor?",
      required=[], forbidden=["reset_password", "restart_vpn", "fix_email_issue", "troubleshoot_printer", "escalate_incident"], outcome=_no_change, expects_escalation=False),
 dict(id="S15", type="Multi-step", message="Username nomsa. My VPN is fine, but Outlook says my mailbox is full.",
      required=["check_email_service", "fix_email_issue"], forbidden=["restart_vpn"], outcome=lambda s: s["users"]["nomsa"]["mailbox_used_pct"] < 95, expects_escalation=False),
]
