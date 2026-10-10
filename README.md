# SentinelAI 🤖

## Autonomous IT Incident Response and Service Desk Agent

SentinelAI is an autonomous IT service-desk agent developed for the AIE580S-DSE580S group assignment.

The system investigates IT incidents using:

- 🤖 AI agent reasoning
- 🔄 ReAct-style agent workflow
- 📚 Retrieval-Augmented Generation (RAG)
- 🛠️ Tool calling
- 🧠 Incident context and memory
- 📊 Testing and evaluation

The current repository contains the **working prototype** and should be used as the starting point for the group's further development.

---

# 🚨 IMPORTANT — GROUP WORK

This is a **group project**.

The current version was initially developed as an end-to-end prototype so that the agent, tools, RAG and dashboard could be tested together.

From this point, we are separating the work according to the original delegation.

### 👨🏾‍💻 Retshidisitswe — AI / Agent Engineering

Main responsibility:

- Gemini integration
- Agent reasoning
- ReAct workflow
- Tool calling
- Agent orchestration
- RAG integration
- Agent decision logic
- AI-related improvements

### 🔧 Zandre — Backend / Integration

Main responsibility:

- Backend architecture
- API endpoints
- Backend integration
- Incident data/state management
- Connecting the agent to backend services
- Improving the supporting workflow
- Integration and deployment setup

The existing backend/supporting code is a **prototype starting point**. It can be reorganised and improved rather than rebuilt from scratch.

### 📊 Mmabotse — Data / Testing / Evaluation

Main responsibility:

- Dataset and knowledge-base preparation
- Data cleaning/preparation
- Test cases
- Agent evaluation
- Performance metrics
- Results
- Graphs/tables for the report
- Testing evidence

### 🤝 Everyone

All members contribute to:

- Documentation
- Testing
- Presentation
- Demonstration
- Final report
- Final integration

---

# 🧩 CURRENT SYSTEM

The current prototype contains:

```text
sentinel-ai/
│
├── app/
│   ├── agent/          # Agent and reasoning components
│   ├── rag/            # RAG / knowledge retrieval
│   └── tools/          # Tools available to the agent
│
├── data/
│   └── knowledge_base/ # IT troubleshooting knowledge
│
├── tests / test files  # Prototype testing
│
├── main.py             # Gemini agent demonstration
├── run_agent.py        # Agent runner
├── requirements.txt    # Python dependencies
└── README.md
```

---

# 🔄 HOW SENTINELAI WORKS

The intended workflow is:

```text
IT Incident
     ↓
SentinelAI Agent
     ↓
Analyse Incident
     ↓
Retrieve Knowledge (RAG)
     ↓
Select Tool / Action
     ↓
Execute Tool
     ↓
Receive Observation
     ↓
Evaluate Result
     ↓
┌───────────────┬────────────────┐
│               │                │
Resolve       Continue       Escalate
```

The important idea is that SentinelAI does not simply return a predefined answer.

The agent can:

1. Understand an incident.
2. Retrieve relevant organisational knowledge.
3. Select an appropriate tool.
4. Execute the tool.
5. Receive the result.
6. Use the result to determine the next action.
7. Resolve the incident or escalate it.

---

# 🛠️ CURRENT TOOLS

The prototype currently contains tools for:

### Knowledge Search
Searches the IT troubleshooting knowledge base.

### Incident Lookup
Retrieves an incident record.

### Incident Update
Updates the incident status/notes.

### Diagnostic Tool
Performs simulated diagnostics for:

- VPN
- Network
- Printer
- Email

### Remediation Tool
Simulates corrective actions such as:

- Clearing a stalled printer queue
- Restarting/reconnecting an email client

### Escalation Tool
Escalates an incident to the appropriate team.

### Incident Summary
Generates a structured incident resolution summary.

---

# 📚 RAG / KNOWLEDGE BASE

The knowledge base currently contains:

```text
data/knowledge_base/

├── vpn_troubleshooting.txt
├── network_troubleshooting.txt
├── printer_troubleshooting.txt
└── email_troubleshooting.txt
```

The RAG system retrieves relevant information from these documents when investigating an incident.

**Note:** The generated `data/vector_db/` directory is intentionally excluded from GitHub. It can be regenerated locally from the knowledge-base documents.

---

# 🖥️ RUNNING THE PROTOTYPE

## 1. Clone the repository

```bash
git clone https://github.com/Asante071/sentinel-ai.git
cd sentinel-ai
```

## 2. Create a virtual environment

```bash
python -m venv .venv
```

## 3. Activate it

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

## 4. Install dependencies

```powershell
pip install -r requirements.txt
```

---

# 🔐 GEMINI API KEY

The Gemini API key must **NOT** be committed to GitHub.

Create a `.env` file in the project root:

```text
GEMINI_API_KEY=YOUR_API_KEY_HERE
```

The `.env` file is already excluded through `.gitignore`.

**Never upload or share the actual API key.**

---

# 🖥️ RUN THE DASHBOARD

From the project directory:

```powershell
python -m app.dashboard
```

Then open:

```text
http://127.0.0.1:8000
```

The dashboard currently demonstrates the local deterministic ReAct workflow.

It allows the group to demonstrate:

- Incident selection
- Knowledge retrieval
- Diagnostics
- Remediation
- Escalation
- Incident summaries
- ReAct workflow evidence

---

# 🤖 RUN THE GEMINI AGENT

The Gemini-based agent can be tested using:

```powershell
python main.py
```

This demonstrates the Gemini agent selecting tools and receiving observations.

The Gemini agent and local dashboard are currently **separate prototype components**.

One of the development goals is to integrate these components properly.

---

# 🎯 WHAT NEEDS TO BE DONE NEXT

## Retshidisitswe — AI / Agent

- [ ] Continue improving Gemini agent
- [ ] Improve tool-selection behaviour
- [ ] Improve agent orchestration
- [ ] Integrate RAG with the agent
- [ ] Ensure the agent can use observations to determine the next action
- [ ] Improve escalation/resolution decision logic
- [ ] Document the agent architecture

## Zandre — Backend / Integration

- [ ] Review existing backend/supporting code
- [ ] Separate backend responsibilities from agent logic
- [ ] Design backend/API structure
- [ ] Implement or improve API endpoints
- [ ] Improve incident state management
- [ ] Connect agent → backend → tools
- [ ] Prepare integration/deployment structure
- [ ] Document backend architecture

## Mmabotse — Data / Testing / Evaluation

- [ ] Review current knowledge-base data
- [ ] Prepare the dataset/evidence required for the assignment
- [ ] Document data sources
- [ ] Perform data quality analysis
- [ ] Prepare test scenarios
- [ ] Define evaluation metrics
- [ ] Run tests
- [ ] Record results
- [ ] Produce graphs/tables for the report

## Everyone

- [ ] Integrate all components
- [ ] Test the complete system
- [ ] Capture screenshots
- [ ] Complete report
- [ ] Prepare presentation
- [ ] Record demo video
- [ ] Prepare final submission

---

# 🧪 CURRENT DEMO SCENARIOS

### INC-1001 — VPN Authentication Failure

Expected behaviour:

```text
Incident
   ↓
VPN knowledge retrieval
   ↓
VPN diagnostic
   ↓
Authentication failure detected
   ↓
Identity & Access escalation
```

### INC-1002 — Printer Not Printing

Expected behaviour:

```text
Incident
   ↓
Printer knowledge retrieval
   ↓
Printer diagnostic
   ↓
Stalled queue detected
   ↓
Clear queue / test print
   ↓
Resolve
```

### INC-1003 — Email Access Problem

Expected behaviour:

```text
Incident
   ↓
Email knowledge retrieval
   ↓
Email diagnostic
   ↓
Mail client requires restart
   ↓
Restart / reconnect
   ↓
Resolve
```

---

# 🌿 GIT WORKFLOW

Please **do not work directly on `main`** unless we agree to.

Create a branch for your work:

```powershell
git checkout -b feature/your-feature-name
```

Example:

```powershell
git checkout -b feature/backend-api
```

After making changes:

```powershell
git add .
git commit -m "Add backend API structure"
git push -u origin feature/backend-api
```

Then create a **Pull Request** on GitHub so the group can review and merge the changes.

---

# ⚠️ IMPORTANT

Do NOT commit:

```text
.env
.venv/
data/vector_db/
__pycache__/
*.pyc
```

The Gemini API key must remain private.

---

# 📌 PROJECT GOAL

The final SentinelAI system should demonstrate an autonomous agent capable of:

> **Receiving an IT incident → reasoning about the problem → retrieving organisational knowledge → selecting and using tools → observing the results → deciding what to do next → resolving or escalating the incident.**

The current repository is the **starting prototype**.

The goal now is to turn the prototype into the final integrated group solution.
