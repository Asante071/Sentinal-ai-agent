"""Usage (from the project folder):  python check_models.py
Asks each Gemini model a tiny question and says which ones answer right now (20 s limit each)."""
import os
import sys
import threading
import time

from dotenv import load_dotenv

load_dotenv()
from google import genai

key = os.getenv("GEMINI_API_KEY")
if not key:
    print("No GEMINI_API_KEY found. Check the .env file.")
    sys.exit(1)

client = genai.Client(api_key=key)
MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
          "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
LIMIT = 20

def try_model(model):
    box = {}

    def work():
        try:
            start = time.time()
            reply = client.interactions.create(model=model, input="Reply with the word OK")
            box["ok"] = (str(reply.output_text).strip()[:20], time.time() - start)
        except Exception as error:
            box["error"] = (str(error).splitlines() or ["error"])[0][:100]

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(LIMIT)
    if thread.is_alive():
        return f"NO ANSWER within {LIMIT} s"
    if "ok" in box:
        return f"WORKS  ({box['ok'][1]:.1f} s)  replied: {box['ok'][0]}"
    return f"ERROR  {box['error']}"


print(f"Testing {len(MODELS)} models, up to {LIMIT} s each...\n")
for name in MODELS:
    print(f"{name:<24} {try_model(name)}", flush=True)
print("\nDone.")
