import re

_SPAM_HEADERS = {"list-unsubscribe", "precedence"}
_MARKETING_MAILERS = {"mailchimp", "sendgrid", "marketo", "constantcontact", "hubspot", "campaignmonitor"}

_ESCALATION_SUBJECT = re.compile(
    r"\b(urgent|critical|failed|failure|wrong[\s_-]*delivery|quality[\s_-]*failure|complaint|recall|rejected|rejection)\b",
    re.IGNORECASE,
)


def rule_classify(subject, sender, headers):
    """
    Fast pre-classifier using regex and header checks.
    Returns a result dict if confident, None if the AI should decide.
    {'type': 'SKIP'} means discard without storing.
    """
    header_keys_lower = {k.lower() for k in headers}

    if _SPAM_HEADERS & header_keys_lower:
        return {"type": "SKIP", "reason": "spam_header"}

    x_mailer = headers.get("x-mailer", "").lower()
    if any(m in x_mailer for m in _MARKETING_MAILERS):
        return {"type": "SKIP", "reason": "marketing_mailer"}

    if _ESCALATION_SUBJECT.search(subject):
        return {"type": "ESCALATION", "subtype": "general"}

    return None
