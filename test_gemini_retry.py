"""Usage (from the project folder):  python test_gemini_retry.py
Simulates Gemini failures. No internet or real Gemini call is made."""
import os
import sys
import time

sys.path.insert(0, ".")
os.environ.setdefault("GEMINI_API_KEY", "dummy-key-for-tests")   # real .env key is not used here
os.environ["GEMINI_WAIT_S"] = "0"                                 # no real waiting in tests

from app.agent.gemini_retry import GeminiUnavailable, create_interaction

results = []

def check(name, condition, detail=""):
    results.append(condition)
    print(f"[{'PASS' if condition else 'FAIL'}] {name} {detail}")

class FakeClient:
    """Pretends to be the Gemini client. `script` lists what each call does, in order."""
    def __init__(self, script):
        self.script, self.calls = list(script), 0
        outer = self

        class _Interactions:
            def create(self, **kwargs):
                outer.calls += 1
                action = outer.script.pop(0) if outer.script else outer.script_last
                if callable(action):
                    return action()
                raise action

        self.interactions = _Interactions()
        self.script_last = RuntimeError("script ran out")


def err503():
    return RuntimeError("Error code: 503 - gemini-3.8-flash is currently experiencing high demand")


os.environ["GEMINI_ATTEMPTS"], os.environ["GEMINI_DEADLINE_S"] = "3", "5"

# 1. temporary 503 twice, then success -> works, 3 calls
c = FakeClient([err503(), err503(), lambda: "OK-RESULT"])
check("503 twice then success is retried", create_interaction(c, model="x") == "OK-RESULT" and c.calls == 3, f"(calls={c.calls})")

# 2. wrong model (404) -> NOT retried, original error passes through
c = FakeClient([RuntimeError("Error code: 404 - This model is no longer available to new users")])
try:
    create_interaction(c, model="x"); passed = False
except RuntimeError:
    passed = c.calls == 1
check("404 wrong model is not retried", passed, f"(calls={c.calls})")

# 3. quota (429) -> NOT retried, passes through to Asante's own 429 handler
c = FakeClient([RuntimeError("Error code: 429 - Rate limit exceeded")])
try:
    create_interaction(c, model="x"); passed = False
except RuntimeError:
    passed = c.calls == 1
check("429 quota is not retried (his handler deals with it)", passed, f"(calls={c.calls})")

# 4. always 503 -> GeminiUnavailable after exactly 3 attempts
c = FakeClient([err503(), err503(), err503()])
try:
    create_interaction(c, model="x"); passed = False
except GeminiUnavailable as e:
    passed = c.calls == 3 and "3 attempts" in str(e)
check("always-503 ends in GeminiUnavailable after 3 attempts", passed, f"(calls={c.calls})")

# 5. hanging call -> time limit stops the wait quickly
os.environ["GEMINI_ATTEMPTS"], os.environ["GEMINI_DEADLINE_S"] = "2", "0.3"
c = FakeClient([lambda: time.sleep(5), lambda: time.sleep(5)])
start = time.time()
try:
    create_interaction(c, model="x"); passed = False
except GeminiUnavailable:
    passed = (time.time() - start) < 3
check("a hanging call is cut off by the time limit", passed, f"(waited {time.time() - start:.1f}s instead of 10s)")

# 6. the real agent: Gemini always down -> friendly stop, returns None, no crash
os.environ["GEMINI_ATTEMPTS"], os.environ["GEMINI_DEADLINE_S"] = "2", "5"
from app.agent.gemini_agent import SentinelAIAgent
agent = SentinelAIAgent()
agent.client = FakeClient([err503(), err503()])
try:
    outcome = agent.process_incident("Incident ID: INC-1001 VPN problem")
    passed = outcome is None
except Exception as e:
    passed = False
    print("   agent crashed with:", repr(e))
check("agent stops cleanly when Gemini stays down", passed)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
