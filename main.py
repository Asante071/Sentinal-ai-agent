import os
import json

from dotenv import load_dotenv
from google import genai

from app.tools.knowledge_search import search_knowledge_base
from app.tools.diagnostic import run_diagnostic

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY is not set in the .env file.")

client = genai.Client(api_key=api_key)


knowledge_search_tool = {
    "type": "function",
    "name": "knowledge_search",
    "description": "Search the SentinelAI IT knowledge base for troubleshooting information.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The IT incident or troubleshooting issue to search for."
            }
        },
        "required": ["query"]
    }
}


diagnostic_tool = {
    "type": "function",
    "name": "run_diagnostic",
    "description": "Run a simulated IT diagnostic test.",
    "parameters": {
        "type": "object",
        "properties": {
            "diagnostic_type": {
                "type": "string",
                "description": "Type of diagnostic test, such as vpn, network, or dns."
            }
        },
        "required": ["diagnostic_type"]
    }
}


tools = [
    knowledge_search_tool,
    diagnostic_tool
]


incident = """
I can't connect to the company VPN.
I have restarted my laptop twice, but it still says authentication failed.
"""


system_instruction = """
You are SentinelAI, an autonomous IT service desk agent.

Your responsibilities are:

1. Analyse IT incidents.
2. Identify the likely problem.
3. Search the knowledge base when troubleshooting information is required.
4. Run diagnostics when technical verification is required.
5. Use the evidence returned by your tools.
6. Decide the appropriate next action.
7. Escalate incidents when they cannot be safely resolved.
8. Provide a final incident resolution summary.

You should investigate the incident using your available tools before making your final decision.
"""


print("\n" + "=" * 60)
print("SENTINELAI AGENT")
print("=" * 60)

interaction = client.interactions.create(
    model="gemini-3.8-flash",
    system_instruction=system_instruction,
    input=incident,
    tools=tools
)


while True:

    function_calls = [
        step for step in interaction.steps
        if step.type == "function_call"
    ]

    if not function_calls:
        break

    function_results = []

    for step in function_calls:

        print("\n" + "-" * 60)
        print("TOOL SELECTED:", step.name)
        print("ARGUMENTS:", step.arguments)

        if step.name == "knowledge_search":

            result = search_knowledge_base(
                step.arguments["query"]
            )

        elif step.name == "run_diagnostic":

            result = run_diagnostic(
                step.arguments["diagnostic_type"]
            )

        else:

            result = "Unknown tool requested."

        print("\nOBSERVATION:")
        print(result)

        function_results.append({
            "type": "function_result",
            "name": step.name,
            "call_id": step.id,
            "result": [
                {
                    "type": "text",
                    "text": json.dumps(result)
                }
            ]
        })

    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        previous_interaction_id=interaction.id,
        input=function_results,
        tools=tools
    )


print("\n" + "=" * 60)
print("SENTINELAI FINAL DECISION")
print("=" * 60)

print(interaction.output_text)