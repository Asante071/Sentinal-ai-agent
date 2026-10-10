import json
import os

from dotenv import load_dotenv
from google import genai

from app.agent.gemini_retry import GeminiUnavailable, create_interaction
from app.agent.tool_definitions import TOOL_DEFINITIONS
from app.agent.tools import TOOL_FUNCTIONS


load_dotenv()


class SentinelAIAgent:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set in the .env file."
            )

        self.client = genai.Client(api_key=api_key)

        self.model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

        self.system_instruction = """
You are SentinelAI, an autonomous IT service desk agent.

Your responsibility is to investigate IT incidents, determine the appropriate
next action, use available tools, and either resolve the incident or escalate it.

Follow a ReAct-style workflow:

1. Understand the incident.
2. Retrieve relevant organisational knowledge using knowledge_search.
3. Select an appropriate diagnostic or investigation tool.
4. Execute the tool.
5. Observe the returned result.
6. Compare the result with the relevant knowledge-base guidance.
7. Decide what action should happen next.
8. Update the incident when appropriate.
9. Escalate the incident when escalation criteria are satisfied.
10. Generate a concise incident resolution summary.

Available tools:

- knowledge_search:
  Searches the organisational knowledge base using semantic RAG retrieval.

- run_diagnostic:
  Runs an available technical diagnostic such as VPN, network, or DNS.

- lookup_incident:
  Retrieves incident details from the incident management system.

- update_incident:
  Updates the incident status and adds investigation notes.

- escalate_incident:
  Escalates an incident to the appropriate support team.

- generate_incident_summary:
  Produces a structured summary of the investigation, actions and outcome.

Important rules:

- Do not invent diagnostic results.
- Use tool results as observations.
- Use the knowledge base to guide troubleshooting and escalation.
- Do not escalate without evidence supporting the escalation.
- When an incident satisfies documented escalation criteria, escalate it to
  the team specified by the knowledge base.
- Keep the investigation focused on the incident.
- Continue using tools until a meaningful resolution or escalation outcome
  has been reached.
- At the end, provide a concise summary containing the incident ID,
  diagnosis, actions taken and outcome.
"""

    def process_incident(self, incident):

        print("\n" + "=" * 70)
        print("SENTINELAI - GEMINI AGENT")
        print("=" * 70)

        # ---------------------------------------------------------
        # INITIAL GEMINI REQUEST
        # ---------------------------------------------------------
        try:

            interaction = create_interaction(
                self.client,
                model=self.model,
                system_instruction=self.system_instruction,
                input=incident,
                tools=TOOL_DEFINITIONS
            )

        except Exception as error:

            error_message = str(error)

            if isinstance(error, GeminiUnavailable):
                print("\n" + "=" * 70)
                print("SENTINELAI AI SERVICE")
                print("=" * 70)
                print(str(error))
                print("The local SentinelAI workflow remains available.")
                print("=" * 70)
                return None

            if (
                "429" in error_message
                or "Rate limit exceeded" in error_message
                or "too_many_requests" in error_message
            ):
                print("\n" + "=" * 70)
                print("SENTINELAI AI SERVICE")
                print("=" * 70)
                print("Gemini API daily quota has been reached.")
                print("The local SentinelAI workflow remains available.")
                print("=" * 70)
                return None

            raise

        # ---------------------------------------------------------
        # REACT TOOL-CALLING LOOP
        # ---------------------------------------------------------
        while True:

            function_calls = [
                step
                for step in interaction.steps
                if step.type == "function_call"
            ]

            # No more tool calls means Gemini has finished
            if not function_calls:
                break

            function_results = []

            # -----------------------------------------------------
            # EXECUTE REQUESTED TOOLS
            # -----------------------------------------------------
            for step in function_calls:

                print(f"\n[ACTION] {step.name}")

                tool_function = TOOL_FUNCTIONS.get(step.name)

                if tool_function is None:

                    result = f"Unknown tool: {step.name}"

                else:

                    try:

                        result = tool_function(**step.arguments)

                    except Exception as error:

                        result = f"Tool execution error: {error}"

                print("[OBSERVATION]")
                print(result)

                function_results.append(
                    {
                        "type": "function_result",
                        "name": step.name,
                        "call_id": step.id,
                        "result": [
                            {
                                "type": "text",
                                "text": json.dumps(result)
                            }
                        ]
                    }
                )

            # -----------------------------------------------------
            # SEND TOOL RESULTS BACK TO GEMINI
            # -----------------------------------------------------
            try:

                interaction = create_interaction(
                    self.client,
                    model=self.model,
                    previous_interaction_id=interaction.id,
                    input=function_results,
                    tools=TOOL_DEFINITIONS
                )

            except Exception as error:

                error_message = str(error)

                if isinstance(error, GeminiUnavailable):
                    print("\n" + "=" * 70)
                    print("SENTINELAI AI SERVICE")
                    print("=" * 70)
                    print(str(error))
                    print("The local SentinelAI workflow remains available.")
                    print("=" * 70)
                    return None

                if (
                    "429" in error_message
                    or "Rate limit exceeded" in error_message
                    or "too_many_requests" in error_message
                ):
                    print("\n" + "=" * 70)
                    print("SENTINELAI AI SERVICE")
                    print("=" * 70)
                    print("Gemini API daily quota has been reached.")
                    print(
                        "The local SentinelAI workflow remains available."
                    )
                    print("=" * 70)
                    return None

                raise

        # ---------------------------------------------------------
        # FINAL RESPONSE
        # ---------------------------------------------------------
        print("\n[FINAL RESPONSE]")
        print(interaction.output_text)

        return interaction.output_text