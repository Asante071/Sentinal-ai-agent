from app.tools.knowledge_search import search_knowledge_base
from app.tools.diagnostic import run_diagnostic
from app.tools.incident_lookup import lookup_incident
from app.tools.incident_update import update_incident
from app.tools.escalation import escalate_incident
from app.tools.incident_summary import generate_incident_summary
from app.agent.classification import classify_incident


def handle_incident(incident_id: str):

    print("\n" + "=" * 60)
    print("SENTINELAI INCIDENT ORCHESTRATOR")
    print("=" * 60)

    # 1. Look up the incident
    print("\n[1] Looking up incident...")
    incident = lookup_incident(incident_id)
    print(incident)

    # 2. Search the knowledge base
    print("\n[2] Searching knowledge base...")
    knowledge = search_knowledge_base(incident)
    print(knowledge)

    # 3. Determine and run diagnostic
    print("\n[3] Running diagnostic...")

    diagnostic_type = classify_incident(incident)

    if diagnostic_type != "unknown":
        diagnostic = run_diagnostic(diagnostic_type)
    else:
        diagnostic = "No automated diagnostic was run: incident classification is required."
    print(diagnostic)

    # 4. Update incident
    print("\n[4] Updating incident...")

    update_result = update_incident(
        incident_id,
        "In Progress",
        f"Knowledge base search and {diagnostic_type} diagnostic completed."
    )

    print(update_result)

    # 5. Determine escalation
    print("\n[5] Evaluating escalation...")

    if "User authentication: FAILED" in diagnostic:

        escalation = escalate_incident(
            incident_id,
            "Identity and Access Team",
            "VPN authentication continues to fail after diagnostic checks."
        )

        print(escalation)

        outcome = "Escalated to Identity and Access Team."

    else:

        outcome = "Incident can continue through standard troubleshooting."

    # 6. Generate final summary
    print("\n[6] Generating incident summary...")

    summary = generate_incident_summary(
        incident_id,
        "Technical diagnostic completed.",
        f"Knowledge base search and {diagnostic_type} diagnostic performed.",
        outcome
    )

    print(summary)

    return summary
