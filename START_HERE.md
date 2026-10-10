# SentinelAI: start here

An IT service-desk agent: a Gemini model reads an employee's problem, searches a knowledge base, checks and fixes things
with IT tools (VPN, account, email, printer), creates and escalates tickets, and remembers past problems. The IT systems
are simulated.

**To try it (about 10 minutes):** open `SETUP.md` and follow **"Quick start for a teammate"** at the top. You need your own
Gemini key (free, aistudio.google.com). Never send your `.env` file to anyone.

- `SETUP.md`: setup, how to run everything, settings, troubleshooting
- `evidence/`: the measured results (evaluation, retrieval, reasoning probe, memory session)
- `results/`: the raw result files of every evaluation run
- `app/`: the agent and the live dashboard; `backend/`, `knowledge_base/`, `evaluation/`: the IT tools, articles and test scenarios
