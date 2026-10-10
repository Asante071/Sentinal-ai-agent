import copy, itertools, secrets
from datetime import datetime
from data import SEED

STATE = copy.deepcopy(SEED)
_ticket_counter = itertools.count(1001)

def reset_state():
    global STATE, _ticket_counter
    STATE = copy.deepcopy(SEED)
    _ticket_counter = itertools.count(1001)

def _res(success, status, message, **data):
    return {"success": success, "status": status, "message": message, "data": data}

def _user(username):
    return STATE["users"].get((username or "").strip().lower())

def _no_user(username):
    return _res(False, "USER_NOT_FOUND", f"No user '{username}' exists in the directory.")

# ---------- Account ----------
def check_account_status(username):
    u = _user(username)
    if not u: return _no_user(username)
    return _res(True, u["account"].upper(), f"Account for {username} is {u['account']}.", account=u["account"])

def reset_password(username):
    u = _user(username)
    if not u: return _no_user(username)
    if u["account"] == "disabled":
        return _res(False, "ACCOUNT_DISABLED", "Account is disabled by IT/HR. Self-service reset not permitted; escalate.")
    was_locked = u["account"] == "locked"
    u["account"] = "active"
    return _res(True, "PASSWORD_RESET", f"Password reset{' and account unlocked' if was_locked else ''}. Temporary password sent to registered phone.",
                temp_ref=secrets.token_hex(3), unlocked=was_locked)

# ---------- VPN ----------
def check_vpn_status(username):
    u = _user(username)
    if not u: return _no_user(username)
    return _res(True, u["vpn"].upper(), f"VPN connection is {u['vpn']} for {username}.", vpn=u["vpn"])

def restart_vpn(username):
    u = _user(username)
    if not u: return _no_user(username)
    if not u["vpn_restart_works"]:
        return _res(False, "RESTART_FAILED", "VPN service restart failed (gateway did not accept session).")
    u["vpn"] = "active"
    return _res(True, "VPN_RESTARTED", "VPN successfully restarted and connection is active.", vpn="active")

# ---------- Email ----------
def check_email_service(username):
    u = _user(username)
    if not u: return _no_user(username)
    full = u["mailbox_used_pct"] >= 95
    return _res(True, "MAILBOX_FULL" if full else "OK",
                f"Email service {u['email_service']}; mailbox {u['mailbox_used_pct']}% used.",
                service=u["email_service"], mailbox_used_pct=u["mailbox_used_pct"])

def fix_email_issue(username):
    u = _user(username)
    if not u: return _no_user(username)
    if u["mailbox_used_pct"] >= 95:
        u["mailbox_used_pct"] = 60
        return _res(True, "MAILBOX_ARCHIVED", "Old mail archived; mailbox now 60% used.", mailbox_used_pct=60)
    return _res(False, "NOTHING_TO_FIX", "No mailbox-capacity problem found; issue is elsewhere (e.g. client profile).")

# ---------- Printer ----------
def check_printer_status(printer_id):
    p = STATE["printers"].get((printer_id or "").upper())
    if not p: return _res(False, "PRINTER_NOT_FOUND", f"No printer '{printer_id}'.")
    return _res(True, p["status"].upper(), f"{printer_id} ({p['location']}) is {p['status']} with {p['queue_jobs']} queued jobs.",
                printer_status=p["status"], queue_jobs=p["queue_jobs"])

def troubleshoot_printer(printer_id):
    p = STATE["printers"].get((printer_id or "").upper())
    if not p: return _res(False, "PRINTER_NOT_FOUND", f"No printer '{printer_id}'.")
    if p["hardware_fault"]:
        return _res(False, "HARDWARE_FAULT", "Remote fix failed: physical fault (e.g. paper jam / toner). Onsite technician needed.")
    p["status"], p["queue_jobs"] = "online", 0
    return _res(True, "PRINTER_RESTORED", "Print queue cleared, spooler restarted; printer online.", printer_status="online")

# ---------- Ticketing ----------
def create_support_ticket(username, category, summary, priority="medium"):
    if not _user(username): return _no_user(username)
    if priority not in ("low", "medium", "high"):
        return _res(False, "INVALID_PRIORITY", "priority must be low, medium or high.")
    tid = f"INC-{next(_ticket_counter)}"
    STATE["tickets"][tid] = {"id": tid, "user": username, "category": category, "summary": summary,
                             "priority": priority, "status": "open", "created": datetime.now().isoformat(timespec="seconds")}
    return _res(True, "TICKET_CREATED", f"Ticket {tid} created.", ticket_id=tid)

def escalate_incident(ticket_id, reason):
    t = STATE["tickets"].get(ticket_id)
    if not t: return _res(False, "TICKET_NOT_FOUND", f"No ticket '{ticket_id}'.")
    t["status"], t["priority"], t["escalation_reason"] = "escalated", "high", reason
    return _res(True, "ESCALATED", f"{ticket_id} escalated to Tier-2 support.", ticket_id=ticket_id)

# ---------- Registry (Gemini function-declaration style) ----------
def _decl(name, fn, desc, props, required):
    return {"name": name, "fn": fn, "declaration": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()}, "required": required}}}

_U = {"username": "Login username, e.g. 'thabo'"}
_P = {"printer_id": "Printer ID, e.g. 'PRN-01'"}
TOOLS = {t["name"]: t for t in [
    _decl("check_account_status", check_account_status, "Check whether a user's account is active, locked or disabled.", _U, ["username"]),
    _decl("reset_password", reset_password, "Reset password and unlock account. Fails for disabled accounts.", _U, ["username"]),
    _decl("check_vpn_status", check_vpn_status, "Check whether the user's VPN connection is active.", _U, ["username"]),
    _decl("restart_vpn", restart_vpn, "Restart the user's VPN session. May fail.", _U, ["username"]),
    _decl("check_email_service", check_email_service, "Check email service health and mailbox usage.", _U, ["username"]),
    _decl("fix_email_issue", fix_email_issue, "Archive old mail to fix a full-mailbox Outlook issue.", _U, ["username"]),
    _decl("check_printer_status", check_printer_status, "Check printer status and queued jobs.", _P, ["printer_id"]),
    _decl("troubleshoot_printer", troubleshoot_printer, "Clear queue and restart spooler. Fails on hardware faults.", _P, ["printer_id"]),
    _decl("create_support_ticket", create_support_ticket, "Create a support ticket. priority: low|medium|high.",
          {**_U, "category": "vpn | account | email | printer | other", "summary": "Short description of the issue and actions taken", "priority": "low, medium or high"},
          ["username", "category", "summary"]),
    _decl("escalate_incident", escalate_incident, "Escalate an existing ticket to Tier-2 support.",
          {"ticket_id": "Ticket ID, e.g. 'INC-1001'", "reason": "Why escalation is needed"}, ["ticket_id", "reason"]),
]}

def get_declarations():
    return [t["declaration"] for t in TOOLS.values()]

def execute_tool(name, args=None):
    """Single entry point for the agent. Logs every call for testing evidence."""
    args = args or {}
    if name not in TOOLS:
        result = _res(False, "UNKNOWN_TOOL", f"Tool '{name}' does not exist.")
    else:
        try:
            result = TOOLS[name]["fn"](**args)
        except TypeError as e:
            result = _res(False, "BAD_ARGUMENTS", f"Invalid arguments: {e}")
    STATE["audit_log"].append({"time": datetime.now().isoformat(timespec="seconds"), "tool": name, "args": args,
                               "success": result["success"], "status": result["status"]})
    return result
