def run_diagnostic(diagnostic_type: str) -> str:
    diagnostics = {
        "vpn": """
        VPN Diagnostic Result:
        - Internet connection: AVAILABLE
        - VPN client: RUNNING
        - VPN gateway: REACHABLE
        - Authentication service: REACHABLE
        - MFA service: REACHABLE
        - User authentication: FAILED
        """,

        "network": """
        Network Diagnostic Result:
        - Network adapter: ACTIVE
        - IP address: ASSIGNED
        - DNS: AVAILABLE
        - Internet connectivity: AVAILABLE
        """,

        "dns": """
        DNS Diagnostic Result:
        - DNS server: REACHABLE
        - Name resolution: WORKING
        - DNS latency: NORMAL
        """,

        "printer": """
        Printer Diagnostic Result:
        - Printer power: ON
        - Network connectivity: AVAILABLE
        - Printer status: ONLINE
        - Print queue: STALLED JOB DETECTED
        - Print spooler: RUNNING
        - Test page: NOT PRINTED
        """,

        "email": """
        Email Diagnostic Result:
        - Network connectivity: AVAILABLE
        - Mail service: REACHABLE
        - Mailbox storage: WITHIN LIMIT
        - Account authentication: SUCCESSFUL
        - Mail client connection: REQUIRES RESTART
        """,
    }

    diagnostic_type = diagnostic_type.lower()

    if diagnostic_type in diagnostics:
        return diagnostics[diagnostic_type]

    return "No diagnostic test is available for this request."
