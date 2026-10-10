"""Usage (from the project folder).

    python run_gateway_agent.py "Hi, my username is thabo. My VPN isn't working."
    python run_gateway_agent.py --memory "Username sipho here, the VPN is down."

Real Gemini + Mmabotse's backend tools + the knowledge base. Prints every step, then the full trace.
Add --memory to switch on long-term memory (history of earlier problems saved in data/agent_memory.db)."""
import sys

sys.path.insert(0, ".")
from app.agent.gateway_agent import GatewayAgent

args = [a for a in sys.argv[1:] if a != "--memory"]
message = " ".join(args) or "Hi, my username is thabo. My VPN isn't working."

memory = None
if "--memory" in sys.argv:
    from app.agent.memory_store import MemoryStore
    memory = MemoryStore()

agent = GatewayAgent(memory=memory)
agent.run(message)

print("\n" + "-" * 70)
print("TRACE (recorded by the gateway)")
for s in agent.gateway.steps:
    print(f"  {s['step']}. {s['tool']:<22} {str(s['status']):<18} success={s['success']}  ({s['seconds']}s)")
