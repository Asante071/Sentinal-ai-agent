"""Usage (from the project folder):  python chat_gateway_agent.py          (memory on)
                                python chat_gateway_agent.py --no-memory

An interactive conversation with the agent. The agent remembers the conversation (short-term memory),
so you can answer its questions, for example give your username when it asks. With memory on it also
keeps a history of earlier problems per user on disk (long-term memory).

Commands:  /history <username>   show what is stored for a user
           /trace                show every tool call so far
           /new                  start a new conversation (long-term memory is kept)
           /quit                 leave"""
import sys

sys.path.insert(0, ".")
from app.agent.gateway_agent import GatewayAgent

memory = None
if "--no-memory" not in sys.argv:
    from app.agent.memory_store import MemoryStore
    memory = MemoryStore()

agent = GatewayAgent(memory=memory)
print(__doc__)
print(f"Model: {agent.model}   Long-term memory: {'ON' if memory else 'OFF'}")
first = True

while True:
    try:
        text = input("\nYou: ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not text:
        continue
    lower = text.lower()
    if lower in ("/quit", "/exit"):
        break
    if lower == "/new":
        agent.new_conversation()
        first = True
        print("New conversation started.")
        continue
    if lower == "/trace":
        for s in agent.gateway.steps:
            print(f"  {s['step']}. {s['tool']:<22} {str(s['status']):<18} success={s['success']}")
        continue
    if lower.startswith("/history"):
        parts = text.split()
        if memory is None or len(parts) < 2:
            print("Usage: /history <username>   (needs memory on)")
        else:
            rows = memory.history(parts[1])
            print(f"{len(rows)} event(s) for {parts[1].lower()}:")
            for r in rows:
                print(f"  {r['ts']}  {r['category'] or '-':<8} {r['event']:<14} {(r['detail'] or '')[:90]}")
        continue
    agent.run(text, banner=first)
    first = False

print("\nTRACE (all turns)")
for s in agent.gateway.steps:
    print(f"  {s['step']}. {s['tool']:<22} {str(s['status']):<18} success={s['success']}")
