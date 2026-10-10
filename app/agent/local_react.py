from app.agent.tools import TOOL_FUNCTIONS
from app.agent.classification import classify_incident


def run_local_react(incident_id: str, return_details: bool = False):
    """Run the deterministic, no-API demo workflow.

    ``return_details`` keeps the command-line exercise backwards compatible
    while allowing the web dashboard to render the evidence behind each step.
    """
    print("\n" + "=" * 70)
    print("SENTINELAI - LOCAL REACT WORKFLOW")
    print("=" * 70)

    # ---------------------------------------------------------
    # STEP 1: LOOK UP INCIDENT
    # ---------------------------------------------------------
    print("\n[THOUGHT]")
    print("I need to understand the incident before deciding what action to take.")

    print("\n[ACTION] lookup_incident")
    incident = TOOL_FUNCTIONS["lookup_incident"](incident_id)
    print(incident)

    # ---------------------------------------------------------
    # STEP 2: SEARCH KNOWLEDGE BASE
    # ---------------------------------------------------------
    print("\n[THOUGHT]")
    print("I should retrieve relevant organisational knowledge for this incident.")

    print("\n[ACTION] knowledge_search")
    knowledge = TOOL_FUNCTIONS["knowledge_search"](incident)
    print(knowledge)

    # ---------------------------------------------------------
    # STEP 3: SELECT DIAGNOSTIC
    # ---------------------------------------------------------
    print("\n[THOUGHT]")

    diagnostic_type = classify_incident(incident)

    if diagnostic_type != "unknown":
        print(
            f"The incident indicates a {diagnostic_type}-related problem. "
            f"I should run the {diagnostic_type} diagnostic."
        )
    else:
        print(
            "The incident does not match an available diagnostic category. "
            "It requires manual service-desk classification."
        )

    # ---------------------------------------------------------
    # STEP 4: RUN DIAGNOSTIC
    # ---------------------------------------------------------
    if diagnostic_type != "unknown":
        print("\n[ACTION] run_diagnostic")
        diagnostic = TOOL_FUNCTIONS["run_diagnostic"](diagnostic_type)
        print(diagnostic)
    else:
        diagnostic = "No automated diagnostic was run: incident classification is required."

    # ---------------------------------------------------------
    # STEP 5: OBSERVE DIAGNOSTIC RESULT
    # ---------------------------------------------------------
    print("\n[OBSERVATION]")
    print(diagnostic)

    # ---------------------------------------------------------
    # STEP 6: EVALUATE OBSERVATIONS AND REMEDIATE WHEN SAFE
    # ---------------------------------------------------------
    print("\n[THOUGHT]")

    remediation_action = None
    remediation_observation = None

    if (
        diagnostic_type == "vpn"
        and "User authentication: FAILED" in diagnostic
    ):
        decision = (
            "Authentication has failed while the required VPN services "
            "are reachable. The knowledge base indicates that this "
            "condition requires escalation to the Identity and Access Team."
        )

        escalation_required = True

    elif diagnostic_type == "printer" and "Print queue: STALLED JOB DETECTED" in diagnostic:
        print(
            "The printer is online but its queue contains a stalled job. "
            "I can safely clear the queue and verify recovery with a test page."
        )
        print("\n[ACTION] clear_print_queue")
        remediation_action = "Clear stalled print queue and run test page"
        remediation_observation = TOOL_FUNCTIONS["clear_print_queue"](incident_id)
        print(remediation_observation)
        print("\n[OBSERVATION]")
        print(remediation_observation)
        decision = "The stalled queue was cleared and the test page printed successfully."
        escalation_required = False

    elif diagnostic_type == "email" and "Mail client connection: REQUIRES RESTART" in diagnostic:
        print(
            "The mail service and account are healthy, but the email client requires a restart. "
            "I can safely restart it and verify that it reconnects."
        )
        print("\n[ACTION] restart_email_client")
        remediation_action = "Restart email client and reconnect"
        remediation_observation = TOOL_FUNCTIONS["restart_email_client"](incident_id)
        print(remediation_observation)
        print("\n[OBSERVATION]")
        print(remediation_observation)
        decision = "The email client restarted and reconnected to the mail service successfully."
        escalation_required = False

    else:
        decision = (
            "The diagnostic result does not meet the current escalation "
            "criteria. The incident can continue through standard troubleshooting."
        )

        escalation_required = False

    print(decision)

    # ---------------------------------------------------------
    # STEP 7: UPDATE INCIDENT
    # ---------------------------------------------------------
    print("\n[ACTION] update_incident")

    update_notes = (
        f"{diagnostic_type.upper()} diagnostic completed.\n"
        f"Diagnostic result:\n{diagnostic}"
    )
    if remediation_action:
        update_notes += f"\nRemediation action: {remediation_action}\nResult:\n{remediation_observation}"

    update_result = TOOL_FUNCTIONS["update_incident"](
        incident_id,
        "In Progress",
        update_notes
    )

    print(update_result)

    # ---------------------------------------------------------
    # STEP 8: ESCALATE IF REQUIRED
    # ---------------------------------------------------------
    if escalation_required:
        print("\n[ACTION] escalate_incident")

        escalation = TOOL_FUNCTIONS["escalate_incident"](
            incident_id,
            "Identity and Access Team",
            "User authentication continues to fail while the "
            "VPN gateway, authentication service and MFA service "
            "are reachable."
        )

        print(escalation)

        outcome = "Escalated to the Identity and Access Team."

    else:
        escalation = None
        outcome = (
            "Resolved through simulated local remediation."
            if remediation_action else "Incident continues through standard troubleshooting."
        )

    # ---------------------------------------------------------
    # STEP 9: GENERATE SUMMARY
    # ---------------------------------------------------------
    print("\n[ACTION] generate_incident_summary")

    summary = TOOL_FUNCTIONS["generate_incident_summary"](
        incident_id,
        f"{diagnostic_type.upper()} diagnostic completed.",
        (
            "Knowledge-base retrieval, diagnostic testing, "
            + (f"{remediation_action.lower()}, and " if remediation_action else "")
            + "incident update were completed."
        ),
        outcome
    )

    print(summary)

    print("\n" + "=" * 70)
    print("REACT WORKFLOW COMPLETE")
    print("=" * 70)

    if return_details:
        return {
            "incident_id": incident_id.upper(),
            "incident": incident,
            "knowledge": knowledge,
            "diagnostic_type": diagnostic_type,
            "diagnostic": diagnostic,
            "decision": decision,
            "remediation_action": remediation_action,
            "remediation_observation": remediation_observation,
            "update_result": update_result,
            "escalation_required": escalation_required,
            "escalation": escalation,
            "outcome": outcome,
            "summary": summary,
        }

    return summary
