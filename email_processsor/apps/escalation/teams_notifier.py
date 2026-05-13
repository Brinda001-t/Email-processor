import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # seconds: 2s, 4s between retries

_PRIORITY_THEME = {
    "HIGH":   "FF0000",  # red
    "MEDIUM": "FFA500",  # orange
    "LOW":    "00AA00",  # green
}

_PRIORITY_ICON = {
    "HIGH":   "🔴",
    "MEDIUM": "🟡",
    "LOW":    "🟢",
}


def send_teams_alert(email, reason="", priority="HIGH"):
    """
    Send a Teams MessageCard alert with a priority badge.
    Returns (True, "") on success, (False, error_message) on failure.

    priority: "HIGH", "MEDIUM", or "LOW"
    """
    webhook = os.getenv("TEAMS_WEBHOOK_URL")
    if not webhook:
        logger.critical("TEAMS_WEBHOOK_URL is not set — skipping Teams alert")
        return False, "TEAMS_WEBHOOK_URL not configured"

    sender = email.get("from", {}).get("emailAddress", {}).get("address", "Unknown")
    body = email.get("body", {}).get("content", "")
    body_preview = body[:500] + "..." if len(body) > 500 else body

    theme_color = _PRIORITY_THEME.get(priority, "FF0000")
    icon = _PRIORITY_ICON.get(priority, "🔴")
    priority_label = f"{icon} {priority}"

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": theme_color,
        "summary": f"[{priority}] Unattended Email Alert",
        "sections": [
            {
                "activityTitle": f"📧 UNATTENDED EMAIL — {priority_label}",
                "activitySubtitle": "No response detected. Please review.",
                "facts": [
                    {"name": "Priority", "value": priority_label},
                    {"name": "Subject",  "value": email.get("subject", "")},
                    {"name": "From",     "value": sender},
                    {"name": "Reason",   "value": reason},
                ],
                "markdown": True,
            },
            {
                "title": "Email Preview",
                "text": body_preview,
                "markdown": True,
            },
        ],
    }

    last_error = "Unknown error"
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.post(webhook, json=payload, timeout=10)
            if resp.status_code in (200, 202):
                return True, ""
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            logger.warning(
                "Teams webhook returned %s (attempt %d/%d)",
                resp.status_code, attempt + 1, _MAX_RETRIES,
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            logger.warning(
                "Teams webhook request failed (attempt %d/%d): %s",
                attempt + 1, _MAX_RETRIES, exc,
            )

        if attempt < _MAX_RETRIES - 1:
            time.sleep(_BACKOFF_BASE ** attempt)

    logger.error("Failed to send Teams alert after %d attempts: %s", _MAX_RETRIES, last_error)
    return False, last_error
