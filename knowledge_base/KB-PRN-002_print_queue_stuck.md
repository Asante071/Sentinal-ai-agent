# Print jobs stuck in queue

**Article ID:** KB-PRN-002
**Category:** Printer
**Keywords:** stuck queue, print jobs pending, spooler

## Symptoms
Print jobs stay 'Pending' or 'Printing' and nothing comes out.

## Resolution steps
1. Check the printer status and queue length (tool: check_printer_status).
2. Run troubleshoot_printer to clear the queue and restart the spooler.
3. Ask the user to resend the jobs they still need.

## When to escalate
If the queue keeps filling and the printer stays in ERROR, escalate.
