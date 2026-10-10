"""Usage (from the project folder):  python try_gateway.py
Tests the gateway with Mmabotse's real tools. No Gemini key needed."""
import sys
sys.path.insert(0, ".")
from app.agent.tool_gateway import ToolGateway, get_tool_definitions

defs = get_tool_definitions()
print(f"{len(defs)} tool definitions:", [d["name"] for d in defs])

g = ToolGateway()
g.call_tool("knowledge_search", {"query": "vpn not connecting"})
g.call_tool("check_vpn_status", {"username": "thabo"})
g.call_tool("restart_vpn", {"username": "thabo"})
g.call_tool("restart_vpn", {"username": "sipho"})      # this one is designed to fail
g.call_tool("not_a_tool", {})                          # unknown tool
g.call_tool("check_vpn_status", {})                    # missing argument

print("\nTRACE")
for s in g.steps:
    print(f"  {s['step']}. {s['tool']:<20} {s['status']:<16} success={s['success']}")
