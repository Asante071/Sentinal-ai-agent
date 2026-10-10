INCIDENTS = {
    "INC-1001": {
        "user": "John Smith",
        "issue": "VPN authentication failure",
        "priority": "High",
        "status": "Open",
        "assigned_team": "Service Desk"
    },
    "INC-1002": {
        "user": "Sarah Jones",
        "issue": "Printer not printing",
        "priority": "Medium",
        "status": "Open",
        "assigned_team": "Service Desk"
    },
    "INC-1003": {
        "user": "David Williams",
        "issue": "Email access problem",
        "priority": "Medium",
        "status": "In Progress",
        "assigned_team": "Messaging Team"
    }
}


def lookup_incident(incident_id: str) -> str:
    incident = INCIDENTS.get(incident_id.upper())

    if not incident:
        return f"Incident {incident_id} was not found."

    return f"""
Incident ID: {incident_id.upper()}
User: {incident['user']}
Issue: {incident['issue']}
Priority: {incident['priority']}
Status: {incident['status']}
Assigned Team: {incident['assigned_team']}
"""