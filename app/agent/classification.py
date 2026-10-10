"""Deterministic incident classification for the local demonstration agent."""

def classify_incident(incident_text: str) -> str:
    """Return a matching diagnostic type, or ``unknown`` when it is unknown.

    An unknown incident must be reviewed rather than being mislabelled as a
    network incident simply because network is the most general diagnostic.
    """
    text = incident_text.lower()

    # Specific service categories come before general connectivity terms.
    if "vpn" in text:
        return "vpn"
    if "printer" in text or "print" in text:
        return "printer"
    if "email" in text or "mailbox" in text or "outlook" in text:
        return "email"
    if "dns" in text or "name resolution" in text:
        return "dns"
    if "network" in text or "connectivity" in text or "internet" in text:
        return "network"
    return "unknown"
