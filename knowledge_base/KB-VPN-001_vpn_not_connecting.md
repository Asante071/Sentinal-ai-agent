# VPN will not connect

**Article ID:** KB-VPN-001
**Category:** VPN
**Keywords:** vpn, cannot connect, connection failed, remote access

## Symptoms
The VPN client shows 'Disconnected', keeps retrying, or fails to connect from home or off-site.

## Resolution steps
1. Confirm the user has working internet (open any public website).
2. Confirm the account is active and not locked (tool: check_account_status).
3. Check the VPN session state (tool: check_vpn_status).
4. If inactive, restart the VPN session (tool: restart_vpn).
5. Ask the user to reconnect and confirm access to an internal resource.

## When to escalate
If restart_vpn fails, or the account is disabled, create a ticket (create_support_ticket) and escalate (escalate_incident).
