"""Rule-based baseline (NO LLM). Keyword intent -> fixed playbook.
Purpose: (1) proves the evaluation harness works, (2) gives the Gemini ReAct agent a baseline to beat.
Agent interface used by the harness:   agent(message: str, call_tool: callable) -> str   (final reply)"""
import re

def _intent(m):
    m = m.lower()
    if any(k in m for k in ("locked", "password", "log in", "sign in", "login")): return "account"
    if "vpn" in m: return "vpn"
    if any(k in m for k in ("outlook", "email", "mailbox")): return "email"
    if "printer" in m or "print" in m: return "printer"
    return None

def _ticket_and_escalate(call, user, cat, summary):
    t = call("create_support_ticket", {"username": user, "category": cat, "summary": summary, "priority": "high"})
    if t["success"]:
        call("escalate_incident", {"ticket_id": t["data"]["ticket_id"], "reason": summary})
        return f"I've escalated this to Tier-2 support as {t['data']['ticket_id']}."
    return "I couldn't create a ticket."

def baseline_agent(message, call):
    u = re.search(r"(?:username(?: is)?|i'?m)\s+(\w+)", message, re.I)
    user = u.group(1).lower() if u else None
    pid = re.search(r"PRN-\d+", message, re.I)
    intent = _intent(message)
    if intent is None:
        return "Sorry, that is outside what I can help with. I handle VPN, account, email and printer issues."
    if intent == "printer":
        if not pid: return "Which printer is affected? Please give the printer ID (e.g. PRN-01)."
        s = call("check_printer_status", {"printer_id": pid.group(0)})
        if not s["success"]: return s["message"]
        r = call("troubleshoot_printer", {"printer_id": pid.group(0)})
        if r["success"]: return "The printer has been restored."
        return _ticket_and_escalate(call, user or "unknown", "printer", r["message"])
    if not user: return "Please tell me your username so I can look into this."
    if intent == "vpn":
        s = call("check_vpn_status", {"username": user})
        if not s["success"]: return f"User not found: {s['message']}"
        if s["status"] == "ACTIVE": return "Your VPN looks active. Try reconnecting."
        r = call("restart_vpn", {"username": user})
        if r["success"]: return "Your VPN has been restored."
        return _ticket_and_escalate(call, user, "vpn", r["message"])
    if intent == "account":
        s = call("check_account_status", {"username": user})
        if not s["success"]: return f"User not found: {s['message']}"
        if s["status"] == "DISABLED": return _ticket_and_escalate(call, user, "account", "Account disabled")
        call("reset_password", {"username": user})
        return "Your password has been reset and the account unlocked."
    if intent == "email":
        s = call("check_email_service", {"username": user})
        if not s["success"]: return f"User not found: {s['message']}"
        if s["status"] == "MAILBOX_FULL":
            call("fix_email_issue", {"username": user}); return "I archived old mail; your mailbox has space again."
        t = call("create_support_ticket", {"username": user, "category": "email", "summary": "Outlook issue, mailbox OK", "priority": "medium"})
        return f"Mailbox is fine, so I opened ticket {t['data'].get('ticket_id')} for further investigation."
