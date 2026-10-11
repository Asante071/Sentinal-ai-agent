"""SentinelAI agent connected to Mmabotse's tools.

Same ReAct loop as Asante's gemini_agent.py (Gemini asks for a tool, we run it, we send the
result back, repeat), but:
  * the input is a user's MESSAGE ("Hi, my username is thabo. My VPN isn't working."),
  * every tool call goes through the ToolGateway to Mmabotse's backend tools (or the RAG),
  * every call is recorded as a step,
  * Gemini calls use the retry / time-limit wrapper,
  * a runaway loop is stopped after MAX_ROUNDS.

For Mmabotse's evaluation harness the module also offers  run(message, call_tool) -> str.
Asante's own gemini_agent.py is not touched.
"""
import json
import os
import re

from dotenv import load_dotenv
from google import genai

from app.agent.gemini_retry import GeminiUnavailable, create_interaction
from app.agent.tool_gateway import ToolGateway, get_tool_definitions

load_dotenv()

MAX_ROUNDS = 12  # most tool-calling rounds in one conversation turn

BASE_INSTRUCTION = """
You are SentinelAI, an autonomous IT service desk agent. Employees describe a problem in
plain language. You investigate with your tools and either fix it or escalate it.

Work in a ReAct loop: read what the message tells you, search the knowledge base, check the
real system state with a read-only tool, act, observe the result, then decide the next step.

Rules, in this order of priority:
1. Missing details come first. VPN, account and email problems need a username. Printer
   problems need a printer ID such as PRN-02. If it is missing, ask for it and call NO tool
   at all, not even knowledge_search.
2. Otherwise, for any support problem, call knowledge_search first. It returns several
   articles: follow the one that matches the problem.
3. Never invent results. Only state what the tools returned. In particular, name an
   escalation team only if a tool result names it, and say it exactly as the tool result
   states it (it may say "Tier-2 support"). Never name any other team.
   Wrong: "escalated to Tier-2 support (Print Services Team)". Right: "escalated to Tier-2 support".
4. Always check status with a check_* tool before you change anything.
5. Only use a tool the evidence calls for. Do not touch services the user did not mention.
6. If an automatic fix fails, or the problem needs a human, call create_support_ticket
   (correct category, one-sentence summary of what you tried) and then call
   escalate_incident with that ticket ID. Escalate only when you have evidence. In the
   escalation reason, describe the problem; do not name a team. After escalating, do not say
   which team or group will handle it or what they will do; say only what the tool result says.
7. Never reset the password of a disabled account. Create a ticket and escalate instead.
8. If a tool reports that the user or the printer was not found, tell the user that the
   username (or printer ID) was not found, ask them to check it, and stop. Change nothing.
9. If the mailbox is healthy but the user still reports an email problem, create a ticket
   (category email) but do not escalate.
10. Requests that are not VPN, account, email or printer support (for example ordering
    hardware) are out of scope: say so politely and do not use any tool. Do not suggest
    portals, systems, forms or contacts that you were not given.
11. Usernames are lower case.

Final answer: 2 to 4 sentences. What you found, what you did, and the outcome. If you used
the knowledge base, finish with a separate last line in exactly this form:
Knowledge base article: <article ID and file name of the result you used>
"""

MEMORY_INSTRUCTION = """

Memory:
- Once you know the username (VPN, account or email problems), call lookup_user_history once.
- Use only what it returns; never invent history.
- If it shows the same kind of problem for this user before, say so in your answer. If an earlier fix
  did not hold (the same problem came back, or an earlier attempt failed), do not just repeat the same
  fix: create a ticket and escalate instead.
"""


def build_instruction(memory_enabled):
    """The agent's instructions. The memory section is only added when memory is switched on."""
    return BASE_INSTRUCTION + (MEMORY_INSTRUCTION if memory_enabled else "")


QUOTA_TEXT = "Sorry, the AI service has reached its usage limit. Please try again later."
DOWN_TEXT = "Sorry, the AI service is not responding right now. I have not changed anything further."
EMPTY_TEXT = "Sorry, the AI service returned an empty answer. Please try again."
LOOP_TEXT = "I could not finish this within the allowed number of steps. Please contact the service desk."


_TEAM_PHRASE = re.compile(r"\b((?:[A-Z][A-Za-z&]*\s+(?:and\s+)?){1,4}Team)\b")


def find_ungrounded_teams(answer, action_text):
    """Team names in the answer that no ACTION tool result mentions.
    (Knowledge-base text is advice, not a record of what happened, so it does not count.)"""
    grounded = action_text.lower()
    found = []
    for match in _TEAM_PHRASE.finditer(answer):
        name = re.sub(r"^(?:the|a|an)\s+", "", match.group(1).strip(), flags=re.I)
        if name.lower() not in grounded and name not in found:
            found.append(name)

    # Also catch additions glued to the team the tool really named, e.g.
    # "Tier-2 support (Print Services / Onsite Maintenance)" or "Tier-2 support / the X group".
    for team in re.findall(r"escalated to ([^.\n]+)", grounded):
        pattern = re.escape(team.strip()) + r"\s*(?:\(([^)]+)\)|/\s*(?:the\s+)?([^.,;\n]+))"
        for match in re.finditer(pattern, answer, flags=re.I):
            extra = (match.group(1) or match.group(2) or "").strip(" *")
            if extra and extra.lower() not in grounded and not any(f.lower() in extra.lower() for f in found):
                found.append(extra)
    return found


def add_citation(answer, sources):
    """If the model did not name an article itself, add the closest match the search returned.
    Labelled as a match, not as 'used', because the model may have followed another result."""
    sources = list(dict.fromkeys(sources))
    lower = answer.lower()
    if not sources or "knowledge base article:" in lower or "closest knowledge base match:" in lower:
        return answer
    return answer.rstrip() + "\n\nClosest knowledge base match: " + ", ".join(sources)


FIX_TOOLS = {"restart_vpn": ("vpn", "username"), "reset_password": ("account", "username"),
             "fix_email_issue": ("email", "username"), "troubleshoot_printer": ("printer", "printer_id")}


class GatewayAgent:
    def __init__(self, call_tool=None, client=None, model=None, memory=None, show_thoughts=None):
        self.memory = memory                      # long-term memory (None = off, e.g. for the evaluation)
        self.gateway = ToolGateway(memory=memory)
        self.call_tool = call_tool or self.gateway.call_tool   # harness can pass its own call_tool
        if client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not set in the .env file.")
            client = genai.Client(api_key=api_key)
        self.client = client
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.tools = get_tool_definitions(include_history=memory is not None)
        self.instruction = build_instruction(memory is not None)
        if show_thoughts is None:
            show_thoughts = os.getenv("SHOW_THOUGHTS", "1") == "1"
        self.show_thoughts = show_thoughts        # ask Gemini for summaries of its reasoning ("thoughts")
        self.events = []                          # thought / action / observation log of the latest run()
        self.last_interaction_id = None           # short-term memory: the conversation so far
        self._resend_instruction = True
        self._tickets = {}
        self._warm_up_rag()

    @staticmethod
    def _warm_up_rag():
        """Load the embedding model now, so the first knowledge_search is not slow."""
        try:
            from app.rag import kb_retriever
            if kb_retriever.kb_available():
                kb_retriever.warm_up()
            else:
                import app.tools.rag_search  # noqa: F401  (Asante's original search)
        except Exception:
            pass  # knowledge_search reports a clear RAG_ERROR itself if the RAG is unavailable

    # ------------------------------------------------------------------
    def _ask(self, **kwargs):
        """One safe Gemini call. Returns (interaction, None) or (None, message_for_user).
        The instructions are sent on EVERY call: as far as we know they apply to one call only, so
        without this the model would stop seeing the rules after the first tool result."""
        call = dict(kwargs)
        if self._resend_instruction or "previous_interaction_id" not in call:
            call["system_instruction"] = self.instruction
        if self.show_thoughts:
            call["generation_config"] = {"thinking_level": os.getenv("THINKING_LEVEL", "medium"),
                                         "thinking_summaries": "auto"}
        try:
            return create_interaction(self.client, model=self.model, tools=self.tools, **call), None
        except GeminiUnavailable as error:
            print("\n[AI SERVICE]", error)
            return None, DOWN_TEXT
        except Exception as error:
            text = str(error)
            if "system_instruction" in text and "system_instruction" in call and "previous_interaction_id" in call:
                self._resend_instruction = False          # this API refuses it on follow-up calls: stop sending it
                print("[NOTE] The API does not accept the instructions on follow-up calls; continuing without them.")
                return self._ask(**kwargs)
            if "generation_config" in call and ("generation_config" in text or "thinking" in text.lower()):
                self.show_thoughts = False                # the API refuses the thinking settings: carry on without
                print("[NOTE] The API did not accept the thinking settings; continuing without visible thoughts.")
                return self._ask(**kwargs)
            if "429" in text or "Rate limit exceeded" in text or "too_many_requests" in text:
                print("\n[AI SERVICE] Gemini quota reached.")
                return None, QUOTA_TEXT
            raise

    @staticmethod
    def _calls_of(interaction):
        steps = getattr(interaction, "steps", None) or []
        return [s for s in steps if getattr(s, "type", None) == "function_call"]

    @staticmethod
    def _text_of(interaction):
        try:
            return interaction.output_text or ""
        except Exception:      # the SDK property can fail when a reply has no steps
            return ""

    def _ask_checked(self, **kwargs):
        """Like _ask, but if Gemini returns nothing at all (no tool call and no text), ask once more.
        Found by the evaluation: an empty reply used to crash the agent (scenario S13)."""
        for attempt in (1, 2):
            interaction, problem = self._ask(**kwargs)
            if problem:
                return None, problem
            if self._calls_of(interaction) or self._text_of(interaction).strip():
                return interaction, None
            print("[NOTE] Gemini returned an empty answer." + (" Asking again." if attempt == 1 else ""))
        return None, EMPTY_TEXT

    @staticmethod
    def _thought_texts(interaction):
        """Readable summaries of the model's reasoning, if Gemini returned any."""
        texts = []
        for step in getattr(interaction, "steps", None) or []:
            if getattr(step, "type", None) != "thought":
                continue
            for item in getattr(step, "summary", None) or []:
                text = item.get("text") if isinstance(item, dict) else getattr(item, "text", "")
                if text:
                    texts.append(str(text).strip())
        return texts

    def _emit_thoughts(self, interaction, verbose):
        for text in self._thought_texts(interaction):
            self.events.append({"kind": "thought", "text": text})
            if verbose:
                flat = " ".join(text.replace("**", "").split())
                print(f"\n[THOUGHT] {flat[:500]}{'...' if len(flat) > 500 else ''}")

    def new_conversation(self):
        """Forget the current conversation (short-term memory). Long-term memory is kept."""
        self.last_interaction_id = None

    def _remember(self, tool, args, result):
        """Write what just happened into long-term memory. Never allowed to break the agent."""
        if self.memory is None:
            return
        try:
            data = result.get("data") or {}
            if tool == "create_support_ticket" and result.get("success"):
                self._tickets[data.get("ticket_id")] = (args.get("username"), args.get("category"))
                self.memory.record(args.get("username"), args.get("category"), "ticket_created",
                                   ticket_ref=data.get("ticket_id", ""), detail=args.get("summary", ""),
                                   outcome=result.get("status", ""))
            elif tool == "escalate_incident" and result.get("success"):
                username, category = self._tickets.get(args.get("ticket_id"), (None, None))
                if username:
                    self.memory.record(username, category, "escalated", ticket_ref=args.get("ticket_id", ""),
                                       detail=args.get("reason", ""), outcome=result.get("status", ""))
            elif tool in FIX_TOOLS:
                category, key = FIX_TOOLS[tool]
                subject = args.get(key)
                if subject:
                    self.memory.record(subject, category, "fixed" if result.get("success") else "fix_failed",
                                       detail=str(result.get("message", "")), outcome=result.get("status", ""))
        except Exception:
            pass

    def run(self, message, verbose=True, banner=True):
        if verbose and banner:
            print("\n" + "=" * 70)
            print("SENTINELAI - GEMINI AGENT (connected to backend tools)")
            print("=" * 70)
            print(f"[MODEL] {self.model}")
        if verbose:
            print(f"[USER] {message}")

        self._sources, self._action_text, self.warnings = [], [], []
        self.events = [{"kind": "user", "text": message}]

        if self.last_interaction_id:   # a follow-up message in the same conversation
            interaction, problem = self._ask_checked(previous_interaction_id=self.last_interaction_id, input=message)
        else:
            interaction, problem = self._ask_checked(input=message)
        if problem:
            return problem

        rounds = 0
        while True:
            self._emit_thoughts(interaction, verbose)
            calls = self._calls_of(interaction)
            if not calls:
                break
            rounds += 1
            if rounds > MAX_ROUNDS:
                return LOOP_TEXT

            results = []
            for step in calls:
                args = dict(step.arguments or {})
                result = self.call_tool(step.name, args)
                self._remember(step.name, args, result)
                if step.name == "knowledge_search":
                    info = result.get("data") or {}
                    source = info.get("citation") or info.get("source")
                    if result.get("status") == "FOUND" and source:
                        self._sources.append(source)
                else:
                    self._action_text.append(str(result.get("message", "")))
                self.events.append({"kind": "action", "tool": step.name, "args": args})
                self.events.append({"kind": "observation", "tool": step.name, "status": result.get("status"),
                                    "message": str(result.get("message"))})
                if verbose:
                    print(f"\n[ACTION] {step.name} {json.dumps(args)}")
                    print(f"[OBSERVATION] {result.get('status')}: {str(result.get('message'))[:300]}")
                for_model = dict(result)
                if step.name == "escalate_incident" and result.get("success"):
                    for_model["note"] = ("Report the team exactly as written in 'message'. "
                                         "No other team is named or assigned; do not mention any other team.")
                results.append({
                    "type": "function_result",
                    "name": step.name,
                    "call_id": step.id,
                    "result": [{"type": "text", "text": json.dumps(for_model)}],
                })

            interaction, problem = self._ask_checked(previous_interaction_id=interaction.id, input=results)
            if problem:
                return problem

        self.last_interaction_id = interaction.id
        answer = self._text_of(interaction)
        self.warnings = [f"The answer names a team that no tool returned: {team}"
                         for team in find_ungrounded_teams(answer, " ".join(self._action_text))]
        answer = add_citation(answer, self._sources)
        self.events.append({"kind": "final", "text": answer})
        if verbose:
            print("\n[FINAL RESPONSE]")
            print(answer)
            for warning in self.warnings:
                print(f"\n[CHECK] {warning}")
        return answer


def run(message, call_tool):
    """Interface used by Mmabotse's evaluation harness:  run(message, call_tool) -> reply.

    The harness's call_tool only knows the backend tools. Knowledge search is not a backend
    tool (it is the RAG), so it is answered here; every other tool goes through the harness's
    call_tool, which is what lets the harness record exactly what the agent did."""
    def routed(name, args=None):
        if name == "knowledge_search":
            return ToolGateway._knowledge_search(args or {})
        return call_tool(name, args)

    return GatewayAgent(call_tool=routed, show_thoughts=os.getenv("EVAL_SHOW_THOUGHTS", "0") == "1").run(message, verbose=False)
