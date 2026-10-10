def escalate_incident(
    incident_id: str,
    team: str,
    reason: str
) -> str:

    return f"""
Incident escalation completed.

Incident ID: {incident_id.upper()}
Escalated To: {team}
Reason: {reason}
Escalation Status: Escalated
"""