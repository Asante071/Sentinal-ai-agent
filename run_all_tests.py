"""Usage (from the project folder):  python run_all_tests.py
Runs every test suite (no Gemini key or internet needed; a stand-in plays Gemini) and prints one line per suite.
Takes 1 to 2 minutes, because each suite loads the embedding model."""
import re
import subprocess
import sys
import time

SUITES = [
    ("Gemini retry protection", "test_gemini_retry.py"),
    ("Agent, tool gateway and answer checks", "test_gateway_agent.py"),
    ("Memory (short-term and long-term)", "test_memory.py"),
    ("Visible thoughts", "test_thoughts.py"),
    ("Live console server", "test_live_dashboard.py"),
    ("Knowledge-base retrieval", "test_kb_retriever.py"),
]

all_ok = True
for title, script in SUITES:
    start = time.time()
    try:
        proc = subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=600)
        output = proc.stdout + proc.stderr
    except Exception as error:
        proc, output = None, f"{type(error).__name__}: {error}"
    found = re.findall(r"(\d+)/(\d+) checks passed", output)
    ok = bool(proc) and proc.returncode == 0 and bool(found) and found[-1][0] == found[-1][1]
    all_ok = all_ok and ok
    result = f"{found[-1][0]}/{found[-1][1]} checks passed" if found else "no result"
    print(f"[{'PASS' if ok else 'FAIL'}] {title:<42} {result}  ({time.time() - start:.0f}s)")
    if not ok:
        print("   --- last lines of output ---")
        print("   " + "\n   ".join(output.strip().splitlines()[-15:]))

print("\nAll suites passed." if all_ok else "\nSome suites failed. See the output above.")
sys.exit(0 if all_ok else 1)
