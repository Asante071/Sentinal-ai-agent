# SentinelAI Mock IT Backend

## Setup
    pip install -r requirements.txt
    python test_scenarios.py        # runs 8 scenarios, writes test_results.csv
    uvicorn api:app --reload        # API + Swagger UI at http://127.0.0.1:8000/docs

## For Asanté (agent integration)
Direct import (simplest):
    from tools import get_declarations, execute_tool, reset_state
    # pass get_declarations() to Gemini as function declarations
    # when Gemini returns a function call:  result = execute_tool(name, args)
    # feed `result` back to the model as the observation

Or over HTTP: GET /tools, POST /tools/{name} with {"args": {...}}, GET /tickets, GET /audit, POST /reset.

## Tool contract
Every tool returns {"success": bool, "status": str, "message": str, "data": {}}.
Tools never raise. Failures return success=false with a status code the agent can reason about.

| Tool | Input | Success status | Failure statuses |
|---|---|---|---|
| check_account_status | username | ACTIVE / LOCKED / DISABLED | USER_NOT_FOUND |
| reset_password | username | PASSWORD_RESET | ACCOUNT_DISABLED, USER_NOT_FOUND |
| check_vpn_status | username | ACTIVE / INACTIVE | USER_NOT_FOUND |
| restart_vpn | username | VPN_RESTARTED | RESTART_FAILED, USER_NOT_FOUND |
| check_email_service | username | OK / MAILBOX_FULL | USER_NOT_FOUND |
| fix_email_issue | username | MAILBOX_ARCHIVED | NOTHING_TO_FIX, USER_NOT_FOUND |
| check_printer_status | printer_id | ONLINE / OFFLINE / ERROR | PRINTER_NOT_FOUND |
| troubleshoot_printer | printer_id | PRINTER_RESTORED | HARDWARE_FAULT, PRINTER_NOT_FOUND |
| create_support_ticket | username, category, summary, [priority] | TICKET_CREATED | INVALID_PRIORITY, USER_NOT_FOUND |
| escalate_incident | ticket_id, reason | ESCALATED | TICKET_NOT_FOUND |

## Mock users / printers (data.py)
thabo: VPN down, fixable | sipho: VPN down, not fixable | lerato: locked | kagiso: disabled | nomsa: mailbox 99%
PRN-01 offline | PRN-02 stuck queue (fixable) | PRN-03 hardware fault
