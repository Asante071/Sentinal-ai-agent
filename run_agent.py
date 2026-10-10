from app.agent.gemini_agent import SentinelAIAgent


def main():

    agent = SentinelAIAgent()

    incident = """
    Incident ID: INC-1001

    The user cannot connect to the company VPN.
    The user has restarted their laptop twice.
    The VPN client reports: "Authentication failed".
    """

    agent.process_incident(incident)


if __name__ == "__main__":
    main()