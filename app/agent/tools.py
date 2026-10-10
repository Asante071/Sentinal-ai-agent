from app.tools.rag_search import search_knowledge
from app.tools.diagnostic import run_diagnostic
from app.tools.incident_lookup import lookup_incident
from app.tools.incident_update import update_incident
from app.tools.escalation import escalate_incident
from app.tools.incident_summary import generate_incident_summary
from app.tools.remediation import (
    clear_print_queue_and_test,
    restart_email_client_and_reconnect,
)


def diagnostic(diagnostic_type: str) -> str:
    return run_diagnostic(diagnostic_type)


def incident_lookup(incident_id: str) -> str:
    return lookup_incident(incident_id)


def incident_update(incident_id: str, status: str, notes: str) -> str:
    return update_incident(incident_id, status, notes)


def incident_escalation(incident_id: str, team: str, reason: str) -> str:
    return escalate_incident(incident_id, team, reason)


def incident_summary(
    incident_id: str,
    diagnosis: str,
    actions_taken: str,
    outcome: str
) -> str:
    return generate_incident_summary(
        incident_id,
        diagnosis,
        actions_taken,
        outcome
    )


def clear_print_queue(incident_id: str) -> str:
    return clear_print_queue_and_test(incident_id)


def restart_email_client(incident_id: str) -> str:
    return restart_email_client_and_reconnect(incident_id)


TOOL_FUNCTIONS = {
    "knowledge_search": search_knowledge,
    "run_diagnostic": diagnostic,
    "lookup_incident": incident_lookup,
    "update_incident": incident_update,
    "escalate_incident": incident_escalation,
    "generate_incident_summary": incident_summary,
    "clear_print_queue": clear_print_queue,
    "restart_email_client": restart_email_client,
}
