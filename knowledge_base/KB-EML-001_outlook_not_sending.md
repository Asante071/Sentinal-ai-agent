# Outlook cannot send or receive email

**Article ID:** KB-EML-001
**Category:** Email
**Keywords:** outlook, cannot send, cannot receive, mailbox full, quota

## Symptoms
Outlook shows 'Mailbox full' or messages stay in the Outbox.

## Resolution steps
1. Check email service health and mailbox usage (tool: check_email_service).
2. If the status is MAILBOX_FULL (95% or more), run fix_email_issue to archive old mail.
3. Ask the user to restart Outlook and send a test email.

## When to escalate
If the mailbox is not full and the service is up, the fault is elsewhere (client profile). Create a ticket.
