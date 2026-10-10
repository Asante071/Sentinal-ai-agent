# Printer shows offline

**Article ID:** KB-PRN-001
**Category:** Printer
**Keywords:** printer offline, not printing, cannot find printer

## Symptoms
A printer is greyed out or shows 'Offline' on the user's computer.

## Resolution steps
1. Get the printer ID from the label on the printer, for example PRN-01.
2. Check the printer status (tool: check_printer_status).
3. If OFFLINE or ERROR, run troubleshoot_printer to restart the spooler.
4. Ask the user to send a test print.

## When to escalate
If troubleshoot_printer returns HARDWARE_FAULT, create a ticket and escalate for an on-site technician.
