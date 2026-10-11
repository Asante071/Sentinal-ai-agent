# SentinelAI: setup and run guide

SentinelAI is an IT service-desk agent. A user types a problem in plain language ("My VPN isn't working"). A Gemini
model reads it, searches a knowledge base, checks and fixes things with IT tools (VPN, account, email, printer),
and creates and escalates tickets when it cannot fix the problem. It remembers the conversation and the history of
earlier problems. The IT environment is simulated (mock users, printers and tickets).

## Quick start for a teammate (about 10 minutes, no changes to the code)
1. Unzip `SentinelAI_share.zip`, open PowerShell in the folder that contains `app`.
2. `python -m venv .venv`, then `.\.venv\Scripts\Activate.ps1`, then `pip install -r requirements.txt` (the first install takes several minutes).
3. Get **your own** Gemini key from Google AI Studio (aistudio.google.com). Copy `.env.example` to `.env` and put your key in it.
   Never use or send someone else's key, and never send your `.env` file.
4. Run `python check_models.py` to see which Gemini models answer right now, and set one that says WORKS in `.env`
   (`GEMINI_MODEL=...`). See "Choosing a model" below.
5. `python run_all_tests.py` should print six `[PASS]` lines (no key needed).
6. `python -m app.live_dashboard`, open http://127.0.0.1:8001, click **Clear agent memory**, then click an example.

## 1. What you need
- **Python 3.10 or newer** (tested on 3.12.10)
- **A Gemini API key**, free from Google AI Studio (aistudio.google.com)
- **Internet** for the first run (downloads the embedding model, about 90 MB) and for every Gemini call
- **About 3 GB of free disk space** (the packages include PyTorch)

## 2. Folder layout (run everything from the folder that contains `app`)
```
app/agent/       the agent: gateway_agent.py (agent), tool_gateway.py (one place all tool calls go through),
                 gemini_retry.py (time limit and retries for Gemini), memory_store.py (long-term memory),
                 gemini_agent.py (the original agent, kept)
app/live_dashboard.py   the live console: a web page that shows the Gemini agent working (see section 5)
app/rag/         kb_retriever.py (knowledge-base search), vector_store.py (original search)
backend/         the mock IT system and its 10 tools
knowledge_base/  the 12 knowledge-base articles (add or edit articles here)
evaluation/      the 15 test scenarios, the evaluation runner and the rule-based baseline
data/            generated files (search index, memory); created automatically
results/         evaluation results (created when you run the evaluation)
```

## 3. Setup (Windows, PowerShell)
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
You should see `(.venv)` at the start of the prompt. If `python` is not found, use `py -3.12 -m venv .venv`.
If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

Mac or Linux: `python3 -m venv .venv`, then `source .venv/bin/activate`, then `pip install -r requirements.txt`.

Create your settings file: copy `.env.example` to a new file named `.env` (same folder as `main.py`) and put your key in it:
```
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.5-flash-lite
```
Never share or commit `.env`.

## 4. Check the installation (no key needed)
```
python run_all_tests.py
```
Six test suites run with a stand-in playing Gemini. Expected: six `[PASS]` lines (6/6, 28/28, 23/23, 12/12, 44/44 and 22/22 checks).
It takes one to two minutes.

## 5. Run the agent
One message:
```
python run_gateway_agent.py "Hi, my username is thabo. My VPN isn't working."
```
A conversation (the agent remembers what you said, and keeps a history per user):
```
python chat_gateway_agent.py
```
Commands inside the chat: `/history <username>`, `/trace`, `/new` (new conversation), `/quit`.
Example users in the simulated system: thabo (VPN needs a restart), sipho (VPN restart fails), lerato (locked account),
kagiso (disabled account), nomsa (mailbox full). Printers: PRN-01, PRN-02 (stuck queue), PRN-03 (hardware fault).

Every run prints each step as it happens: `[THOUGHT]` (a summary of the agent's reasoning before it acts), `[ACTION]`
(the tool and its arguments), `[OBSERVATION]` (what it returned), then `[FINAL RESPONSE]` and a trace of all tool calls. Long-term memory is switched on with `--memory` for
`run_gateway_agent.py` and is on by default in the chat.

### The live console (in the browser): the project's dashboard
```
python -m app.live_dashboard
```
Then open **http://127.0.0.1:8001**. Type a problem (or click one of the examples) and the page shows, as it happens, each
THOUGHT (the model's reasoning summary), ACTION (the tool and its arguments) and OBSERVATION (the tool's real result), then
the final answer. What it adds:
- **Knowledge matches as cards.** A knowledge search shows the articles found, with a bar for how close each one is.
- **An outcome banner** on every answer (Resolved, Escalated, Ticket opened, or Answered with no system change). It is worked
  out from what the tools actually did, not from what the model says, with the number of tool calls and the time taken.
- **Technician and Employee views.** The button at the top right switches between the full reasoning and only the conversation.
- **Tickets, tool audit log and memory.** The tickets in the simulated system, every tool call, and what the agent remembers
  about a user.
- **Live or offline, always labelled.** Every answer says whether it came from a live Gemini run (with the model name) or from
  the offline workflow, and a line under the activity heading explains the two border styles.
- **Offline workflow.** Asante's scripted workflow (no AI, three preset incidents) plays in the same timeline, marked as
  offline. It follows fixed rules, so it works without Gemini and gives the same result every time.
  Its knowledge search uses Asante's original index, which is not shipped. Build it once (it takes a few seconds):
  `python -c "from app.rag.vector_store import build_index; build_index()"`

"New conversation" starts a fresh conversation (memory of past problems is kept). "Reset simulated systems" puts the mock
users, printers and tickets back to the start. "Clear agent memory" makes the agent forget past problems; use it before a demo,
because an earlier fix for the same user changes what the agent does. It serves this computer only and handles one conversation
at a time. Add `--no-memory` to switch long-term memory off; set `CONSOLE_PORT` to use another port. Press Ctrl+C to stop it.

## 6. Run the evaluation (needs the key; takes 5 to 15 minutes)
```
python evaluation/run_evaluation.py --agent app.agent.gateway_agent:run --name my_run
```
Results are written to `results/my_run_results.csv` and `results/my_run_summary.json`. The rule-based baseline's results
are in `evaluation/results/`. Memory is off during the evaluation so the scenarios stay independent.

## 7. The knowledge base
Put articles as `.md` or `.txt` files in `knowledge_base/`. The search index rebuilds itself when an article changes.
Each article should have a `# Title`, an `**Article ID:**` and a `**Category:**` line so answers can cite it.
`python eval_retrieval.py` measures whether the search finds the right article for 15 sample questions.

## 8. Settings (all optional, in `.env`)
| Setting | Default | Meaning |
|---|---|---|
| `GEMINI_MODEL` | gemini-3.5-flash-lite | Which Gemini model to use. Run `python check_models.py` to see which ones answer today |
| `GEMINI_DEADLINE_S` | 40 | Seconds to wait for one Gemini answer |
| `GEMINI_ATTEMPTS` | 3 | Tries before giving up |
| `KB_DIR` | knowledge_base | Folder with the articles |
| `KB_MAX_DISTANCE` | off | Ignore search results farther than this |
| `MEMORY_DB` | data/agent_memory.db | Where long-term memory is stored |
| `SHOW_THOUGHTS` | 1 | 1 shows the agent's reasoning as `[THOUGHT]` lines, 0 turns it off |
| `THINKING_LEVEL` | medium | How much Gemini thinks before acting. Measured: `low` returned a readable reasoning summary in 1 of 3 calls, `medium` and `high` in 3 of 3 |
| `EVAL_SHOW_THOUGHTS` | 0 | Set to 1 to run the evaluation with thoughts on (off by default, so results stay comparable) |

### Choosing a model
The agent works with any Gemini model that supports tool calling through the Interactions API. The model is one setting
(`GEMINI_MODEL`), so changing it needs no change to the code. Availability changes through the day. On 9 October 2026,
four checks of six models (`python check_models.py`) answered within 20 seconds this many times:

| Model | Answered | Model | Answered |
|---|---|---|---|
| gemini-3.8-flash | 1 of 4 | gemini-3.5-flash | 3 of 4 |
| gemini-3.7-flash | 2 of 4 | gemini-3.5-flash-lite | 2 of 4 |
| gemini-3.6-flash | 0 of 4 | gemini-3.1-flash-lite | 4 of 4 |

The results in `results/` were measured on **gemini-3.5-flash-lite**, which was responding when the evaluation ran. If the
model you chose does not answer (the console says "AI service is not responding"), run `python check_models.py`, pick one that
says WORKS, restart the program, and note which model any result came from. Another model can differ in speed and in
how it chooses tools, so results from different models should not be mixed in one table.

## 9. Troubleshooting
| What you see | What it means and what to do |
|---|---|
| `'python' is not recognized` or the Microsoft Store opens | Install Python from python.org (tick "Add python.exe to PATH") or use `py -3.12` |
| `Could not open requirements file` | You are in the wrong folder. `cd` into the folder that contains `app` and `requirements.txt` |
| `GEMINI_API_KEY is not set` | `.env` is missing or not in the project folder next to `main.py` |
| `Model '...' not found` | A typo in `GEMINI_MODEL`. Note that `gemini-2.5-flash` is not available to new keys |
| `[RETRY] ... no answer within 40 s` or error 503 "high demand" | Google is overloaded. The agent retries and then stops cleanly. Try again later or pick another model (`python check_models.py`) |
| `[NOTE] Gemini returned an empty answer. Asking again.` | Handled automatically; no action needed |
| `No articles found in 'knowledge_base'` | The `knowledge_base` folder is missing from the project folder |
| `ModuleNotFoundError: app` | Run commands from the project folder, not from inside `app` |
| First search takes 10 to 30 seconds | The embedding model loads once at the start of each run |
| Warning about `HF_TOKEN` | Harmless |
| Live console: `address already in use` | Another program uses port 8001. Set `CONSOLE_PORT` to another number, for example 8002 |

## 10. Known limitations
- The agent is a language model: its choices vary between runs (see the evaluation results).
- The IT environment is simulated; the tools do not touch real systems.
- Gemini speed and availability vary during the day; the larger Gemini models were timing out on the test day, so the
  results were measured on `gemini-3.5-flash-lite`.
- The first prototype page (`app/dashboard.py`, port 8000) is superseded by the live console, which includes its scripted
  workflow as the Offline workflow mode. Use the live console, or the command-line scripts, to see the agent.
