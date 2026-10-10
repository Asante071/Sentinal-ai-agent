TOOL_DEFINITIONS = [

    {
        "type": "function",
        "name": "knowledge_search",
        "description": (
            "Search the organisational IT knowledge base for "
            "troubleshooting procedures and technical guidance."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The IT issue or symptom to search for."
                }
            },
            "required": ["query"]
        }
    },

    {
        "type": "function",
        "name": "run_diagnostic",
        "description": (
            "Run a simulated technical diagnostic to investigate "
            "an IT incident."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "diagnostic_type": {
                    "type": "string",
                    "description": (
                        "Diagnostic type such as vpn, network, or dns."
                    )
                }
            },
            "required": ["diagnostic_type"]
        }
    },

    {
        "type": "function",
        "name": "lookup_incident",
        "description": (
            "Retrieve the details and current status of an IT incident."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string",
                    "description": "The incident identifier, for example INC-1001."
                }
            },
            "required": ["incident_id"]
        }
    },

    {
        "type": "function",
        "name": "update_incident",
        "description": (
            "Update the status and investigation notes of an IT incident."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string"
                },
                "status": {
                    "type": "string",
                    "description": "New incident status."
                },
                "notes": {
                    "type": "string",
                    "description": "Notes describing the action taken."
                }
            },
            "required": [
                "incident_id",
                "status",
                "notes"
            ]
        }
    },

    {
        "type": "function",
        "name": "escalate_incident",
        "description": (
            "Escalate an unresolved IT incident to the appropriate "
            "support team."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string"
                },
                "team": {
                    "type": "string",
                    "description": "The team that should receive the escalation."
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for escalation."
                }
            },
            "required": [
                "incident_id",
                "team",
                "reason"
            ]
        }
    },

    {
        "type": "function",
        "name": "generate_incident_summary",
        "description": (
            "Generate a structured summary of the incident diagnosis, "
            "actions taken, and outcome."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {
                    "type": "string"
                },
                "diagnosis": {
                    "type": "string"
                },
                "actions_taken": {
                    "type": "string"
                },
                "outcome": {
                    "type": "string"
                }
            },
            "required": [
                "incident_id",
                "diagnosis",
                "actions_taken",
                "outcome"
            ]
        }
    },

    {
        "type": "function",
        "name": "clear_print_queue",
        "description": "Clear a stalled print queue and run a simulated test page.",
        "parameters": {
            "type": "object",
            "properties": {"incident_id": {"type": "string"}},
            "required": ["incident_id"]
        }
    },

    {
        "type": "function",
        "name": "restart_email_client",
        "description": "Restart the email client and run a simulated reconnect check.",
        "parameters": {
            "type": "object",
            "properties": {"incident_id": {"type": "string"}},
            "required": ["incident_id"]
        }
    }

]
{
    "type": "function",
    "name": "knowledge_search",
    "description": (
        "Search the SentinelAI organisational knowledge base using "
        "semantic retrieval. Use this tool to find relevant troubleshooting "
        "procedures, escalation criteria, and technical guidance for an incident."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The incident or technical problem to search for."
            }
        },
        "required": ["query"]
    }
},
