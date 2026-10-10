"""Usage (from the project folder):  python probe_thoughts.py
READ-ONLY probe (3 Gemini calls, nothing is changed). Shows what Gemini returns for each step and whether it can
return its reasoning ("thoughts"), so the visible-thought feature is built on facts and not on a guess."""
import json
import os
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv()
from google import genai

from app.agent.gemini_retry import create_interaction
from app.agent.gateway_agent import BASE_INSTRUCTION
from app.agent.tool_gateway import get_tool_definitions

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MESSAGE = "Hi, my username is thabo. My VPN isn't working."
print("Model:", model)

def show(step):
    try:
        data = step.model_dump(exclude_none=True)
    except Exception:
        data = {k: getattr(step, k) for k in dir(step) if not k.startswith("_") and not callable(getattr(step, k, None))}
    return json.dumps(data, default=str)[:700]


def attempt(label, **extra):
    print(f"\n=== {label} ===")
    try:
        interaction = create_interaction(client, model=model, input=MESSAGE, system_instruction=BASE_INSTRUCTION,
                                         tools=get_tool_definitions(), **extra)
    except Exception as error:
        print("ERROR:", (str(error).splitlines() or ["?"])[0][:400])
        return
    steps = list(getattr(interaction, "steps", None) or [])
    print(f"{len(steps)} step(s) returned")
    for i, step in enumerate(steps, 1):
        print(f"  step {i}: type = {getattr(step, 'type', '?')}")
        print("     ", show(step))
    try:
        print("  output_text:", repr(interaction.output_text)[:300])
    except Exception as error:
        print("  output_text: not available", type(error).__name__)


attempt("A: normal request (what we send today)")
attempt("B: ask for thought summaries", generation_config={"thinking_summaries": "auto"})
attempt("C: low thinking level + summaries", generation_config={"thinking_level": "low", "thinking_summaries": "auto"})
print("\nDone.")
