import re

_SPAM_HEADERS = {"list-unsubscribe", "precedence"}
_MARKETING_MAILERS = {"mailchimp", "sendgrid", "marketo", "constantcontact", "hubspot", "campaignmonitor"}

_COA_SUBJECT = re.compile(
    r"\b(certificate[\s_-]*of[\s_-]*analysis|coa|test[\s_-]*report|quality[\s_-]*report|lot[\s_-]*certificate|material[\s_-]*report)\b",
    re.IGNORECASE,
)
_COA_AMENDMENT = re.compile(
    r"\b(amendment|amended|revised|revision|updated|update|correction|corrected|reissued|superseded)\b",
    re.IGNORECASE,
)
_ORDER_SUBJECT = re.compile(
    r"\b(purchase[\s_-]*order|po[\s_-]*#|po#|order[\s_-]*status|order[\s_-]*confirmation|order[\s_-]*inquiry|order[\s_-]*update|delivery[\s_-]*status)\b",
    re.IGNORECASE,
)
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

    if _COA_SUBJECT.search(subject) and _COA_AMENDMENT.search(subject):
        return {"type": "COA", "subtype": "amendment"}

    if _COA_SUBJECT.search(subject):
        return {"type": "COA", "subtype": "new"}

    if _ORDER_SUBJECT.search(subject):
        return {"type": "ORDER", "subtype": "status_check"}

    if _ESCALATION_SUBJECT.search(subject):
        return {"type": "ESCALATION", "subtype": "general"}

    return None
