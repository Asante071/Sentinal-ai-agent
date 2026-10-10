"""Single gateway between the Gemini agent and every tool.

Uses the IT tools in the project's backend/ folder (tools.py and data.py, written by Mmabotse).

The agent never calls a tool function directly. It calls gateway.call_tool(name, args), which
  1. routes the call: knowledge_search -> Asante's ChromaDB RAG, everything else -> Mmabotse's tools,
  2. records the step (tool, arguments, status) so the trace can be displayed and evaluated,
  3. never raises: failures come back as a result the agent can read and react to.
"""
import os
import re
import sys
import time

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import tools as backend_tools  # Mmabotse's backend/tools.py: execute_tool, get_declarations, reset_state

KNOWLEDGE_TOOL = {
    "type": "function",
    "name": "knowledge_search",
    "description": "Search the IT knowledge base for the correct troubleshooting procedure. Use this FIRST.",
    "parameters": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "The IT problem in plain words."}},
        "required": ["query"],
    },
}


HISTORY_TOOL = {
    "type": "function",
    "name": "lookup_user_history",
    "description": "Look up what happened earlier for this user (past fixes, tickets, escalations). "
                   "Use it once you know the username.",
    "parameters": {
        "type": "object",
        "properties": {"username": {"type": "string", "description": "The employee's username, lower case."}},
        "required": ["username"],
    },
}


def get_tool_definitions(include_history=False):
    """Tool list in the format Asante's agent sends to the Gemini Interactions API.
    The history tool is only offered when long-term memory is switched on."""
    extra = [HISTORY_TOOL] if include_history else []
    return [KNOWLEDGE_TOOL] + extra + [{"type": "function", **d} for d in backend_tools.get_declarations()]


def _fail(status, message):
    return {"success": False, "status": status, "message": message, "data": {}}


class ToolGateway:
    def __init__(self, memory=None):
        self.steps = []  # the trace: one entry per tool call
        self.memory = memory

    def call_tool(self, name, args=None):
        args = args if isinstance(args, dict) else {}
        started = time.time()
        try:
            if name == "knowledge_search":
                result = self._knowledge_search(args)
            elif name == "lookup_user_history":
                result = self._lookup_history(args)
            else:
                result = backend_tools.execute_tool(name, args)  # also writes Mmabotse's audit log
        except Exception as e:  # nothing may crash the agent loop
            result = _fail("GATEWAY_ERROR", f"{type(e).__name__}: {e}")
        self.steps.append({
            "step": len(self.steps) + 1,
            "tool": name,
            "args": args,
            "success": result.get("success"),
            "status": result.get("status"),
            "message": result.get("message"),
            "seconds": round(time.time() - started, 3),
        })
        return result

    def _lookup_history(self, args):
        username = args.get("username")
        if self.memory is None:
            return _fail("MEMORY_OFF", "Long-term memory is not enabled.")
        if not isinstance(username, str) or not username.strip():
            return _fail("BAD_ARGUMENTS", "lookup_user_history needs a non-empty 'username'.")
        username = username.strip().lower()
        rows = self.memory.history(username, limit=10)
        if not rows:
            return {"success": True, "status": "NO_HISTORY", "data": {"events": [], "count": 0},
                    "message": f"No earlier events are recorded for {username}."}
        lines = [f"{r['ts']}  {r['category'] or '-'}  {r['event']}  {(r['detail'] or '')[:110]}" for r in rows]
        return {"success": True, "status": "HISTORY_FOUND", "data": {"events": rows, "count": len(rows)},
                "message": f"{len(rows)} earlier event(s) for {username}, newest first:\n" + "\n".join(lines)}

    @staticmethod
    def _knowledge_search(args):
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            return _fail("BAD_ARGUMENTS", "knowledge_search needs a non-empty 'query'.")
        try:
            from app.rag import kb_retriever  # generic retriever over the knowledge_base folder
            if kb_retriever.kb_available():
                results = kb_retriever.search_kb(query, top_k=3)
                if not results:
                    return {"success": True, "status": "NO_RESULTS",
                            "message": "No relevant knowledge-base information was found.", "data": {}}
                top = results[0]
                return {"success": True, "status": "FOUND", "message": kb_retriever.format_results(results),
                        "data": {"source": top["file"], "article_id": top["id"],
                                 "citation": f"{top['id']} ({top['file']})",
                                 "sources": [r["file"] for r in results], "distance": top["distance"]}}
            # no knowledge_base folder: fall back to Asante's original search over data/knowledge_base
            from app.tools.rag_search import search_knowledge
            text = search_knowledge(query)
        except Exception as e:
            return _fail("RAG_ERROR", f"Knowledge search failed: {type(e).__name__}: {e}")
        if text.startswith("No relevant"):
            return {"success": True, "status": "NO_RESULTS", "message": text, "data": {}}
        source = re.search(r"Source:\s*(.+)", text)
        distance = re.search(r"Chroma distance:\s*([\d.]+)", text)
        return {"success": True, "status": "FOUND", "message": text,
                "data": {"source": source.group(1).strip() if source else None,
                         "distance": float(distance.group(1)) if distance else None}}
