def generate_incident_summary(
    incident_id: str,
    diagnosis: str,
    actions_taken: str,
    outcome: str
) -> str:

    return f"""
Incident Resolution Summary
===========================

Incident ID: {incident_id.upper()}

Diagnosis:
{diagnosis}

Actions Taken:
{actions_taken}

Outcome:
{outcome}
"""