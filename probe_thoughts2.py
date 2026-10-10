"""Usage (from the project folder):  python probe_thoughts2.py
READ-ONLY measurement (9 Gemini calls, nothing is changed, about 2 to 4 minutes).
For three thinking levels and three typical messages: does Gemini return a readable reasoning summary,
how long does it take, and does the agent's own code read it correctly?"""
import os
import sys
import time

sys.path.insert(0, ".")
os.environ.setdefault("GEMINI_DEADLINE_S", "60")
from dotenv import load_dotenv

load_dotenv()
from google import genai

from app.agent.gateway_agent import BASE_INSTRUCTION, GatewayAgent
from app.agent.gemini_retry import create_interaction
from app.agent.tool_gateway import get_tool_definitions

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MESSAGES = [
    "Hi, my username is thabo. My VPN isn't working.",
    "Username sipho here, the VPN is down and I can't reach the file server.",
    "I'm thabo. The Finance printer PRN-03 is showing an error and won't print.",
]
print("Model:", model, "\n")
print(f"{'level':<8} {'msg':<4} {'seconds':>8}  {'thought steps':>13}  {'summary chars':>13}  first words")

totals = {}
for level in ("low", "medium", "high"):
    for number, message in enumerate(MESSAGES, 1):
        start = time.time()
        try:
            interaction = create_interaction(
                client, model=model, input=message, system_instruction=BASE_INSTRUCTION, tools=get_tool_definitions(),
                generation_config={"thinking_level": level, "thinking_summaries": "auto"})
        except Exception as error:
            print(f"{level:<8} {number:<4} {time.time() - start:>8.1f}  ERROR: {(str(error).splitlines() or ['?'])[0][:90]}")
            continue
        steps = [s for s in (getattr(interaction, "steps", None) or []) if getattr(s, "type", None) == "thought"]
        texts = GatewayAgent._thought_texts(interaction)          # the agent's own reader
        chars = sum(len(t) for t in texts)
        snippet = " ".join(texts[0].replace("**", "").split())[:60] if texts else "(none)"
        print(f"{level:<8} {number:<4} {time.time() - start:>8.1f}  {len(steps):>13}  {chars:>13}  {snippet}")
        totals.setdefault(level, []).append(chars > 0)

print("\nSummary: how often a readable summary came back")
for level, flags in totals.items():
    print(f"  {level:<8} {sum(flags)} of {len(flags)}")
