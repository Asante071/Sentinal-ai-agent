# Account locked out

**Article ID:** KB-ACC-001
**Category:** Account
**Keywords:** locked out, too many attempts, cannot log in

## Symptoms
The user sees 'Your account has been locked' after several failed sign-in attempts.

## Resolution steps
1. Check the account status (tool: check_account_status).
2. If status is LOCKED, run reset_password to unlock and issue a temporary password.
3. Tell the user the temporary password is sent to their registered phone and must be changed at first sign-in.

## When to escalate
If the account is DISABLED, self-service reset is not permitted. Create a ticket and escalate.
