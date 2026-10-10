# VPN rejects username or password

**Article ID:** KB-VPN-003
**Category:** VPN
**Keywords:** vpn login failed, invalid credentials, authentication failed

## Symptoms
VPN connects to the gateway but shows 'authentication failed' or 'invalid credentials'.

## Resolution steps
1. Check the account status (tool: check_account_status). A locked account is the most common cause.
2. If locked, reset the password and unlock (tool: reset_password).
3. Ask the user to retry the VPN with the new temporary password.

## When to escalate
If the account is disabled, do not reset. Create a ticket and escalate, because disabled accounts are controlled by HR/IT.
