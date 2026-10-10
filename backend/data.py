"""Seed data for the mock IT environment. Edit freely to add scenarios."""

SEED = {
    "users": {
        # VPN down, restart works  -> agent should fix it
        "thabo":  {"account": "active",   "vpn": "inactive", "vpn_restart_works": True,  "mailbox_used_pct": 40, "email_service": "up"},
        # Locked account           -> agent should unlock / reset password
        "lerato": {"account": "locked",   "vpn": "active",   "vpn_restart_works": True,  "mailbox_used_pct": 30, "email_service": "up"},
        # VPN down, restart fails  -> agent should escalate
        "sipho":  {"account": "active",   "vpn": "inactive", "vpn_restart_works": False, "mailbox_used_pct": 55, "email_service": "up"},
        # Mailbox nearly full      -> Outlook problems
        "nomsa":  {"account": "active",   "vpn": "active",   "vpn_restart_works": True,  "mailbox_used_pct": 99, "email_service": "up"},
        # Disabled account         -> cannot self-service reset, must escalate
        "kagiso": {"account": "disabled", "vpn": "inactive", "vpn_restart_works": True,  "mailbox_used_pct": 20, "email_service": "up"},
    },
    "printers": {
        "PRN-01": {"location": "2nd floor", "status": "offline", "queue_jobs": 0,  "hardware_fault": False},
        "PRN-02": {"location": "Reception", "status": "error",   "queue_jobs": 14, "hardware_fault": False},
        "PRN-03": {"location": "Finance",   "status": "error",   "queue_jobs": 2,  "hardware_fault": True},
    },
    "tickets": {},
    "audit_log": [],
}
