"""Safe, simulated remediation actions used by the local SentinelAI demo."""


def clear_print_queue_and_test(incident_id: str) -> str:
    return f"""
Printer Remediation Result:
- Incident: {incident_id.upper()}
- Stalled print queue: CLEARED
- Print spooler: RUNNING
- Test page: PRINTED SUCCESSFULLY
"""


def restart_email_client_and_reconnect(incident_id: str) -> str:
    return f"""
Email Remediation Result:
- Incident: {incident_id.upper()}
- Mail client: RESTARTED
- Mail service connection: RECONNECTED
- Account synchronization: SUCCESSFUL
"""
