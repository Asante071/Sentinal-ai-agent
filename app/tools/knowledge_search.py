def search_knowledge_base(query: str) -> str:
    knowledge = {
        "vpn": """
        VPN Troubleshooting:
        1. Confirm the user has an active internet connection.
        2. Verify the VPN client is running.
        3. Confirm the user's credentials are valid.
        4. Check whether MFA authentication is successful.
        5. Restart the VPN client.
        6. If authentication continues to fail, escalate to the Identity and Access team.
        """,

        "password": """
        Password Reset:
        1. Verify the user's identity.
        2. Check whether the account is locked.
        3. Reset the password using the approved password reset process.
        4. Confirm the user can authenticate successfully.
        """,

        "printer": """
        Printer Troubleshooting:
        1. Check whether the printer is powered on.
        2. Verify network connectivity.
        3. Check the printer queue for stuck jobs.
        4. Restart the print spooler if necessary.
        5. Remove and reconnect the printer if the issue persists.
        """,

        "email": """
        Email Troubleshooting:
        1. Verify network connectivity.
        2. Check whether the mailbox has reached its storage limit.
        3. Restart the mail application.
        4. Check account authentication.
        5. Escalate persistent mailbox issues to the messaging team.
        """
    }

    query_lower = query.lower()

    for keyword, information in knowledge.items():
        if keyword in query_lower:
            return information

    return "No relevant knowledge-base article was found for this incident."