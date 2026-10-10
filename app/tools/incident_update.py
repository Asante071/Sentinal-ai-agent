from app.tools.incident_lookup import INCIDENTS


def update_incident(
    incident_id: str,
    status: str,
    notes: str
) -> str:

    incident_id = incident_id.upper()

    if incident_id not in INCIDENTS:
        return f"Incident {incident_id} was not found."

    INCIDENTS[incident_id]["status"] = status
    INCIDENTS[incident_id]["notes"] = notes

    return f"""
Incident updated successfully.

Incident ID: {incident_id}
New Status: {status}
Notes: {notes}
"""