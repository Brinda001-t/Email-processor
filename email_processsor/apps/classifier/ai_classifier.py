import json
import logging

import openai

from apps.core.openai_client import client, strip_json_fences

logger = logging.getLogger(__name__)


def classify_email(email_text):
    prompt = f"""
You are an email classifier. Classify the email as ESCALATION or OTHER.

- ESCALATION: Contains an urgent issue, complaint, or problem requiring immediate attention.
  Look for: failed tests, wrong delivery, order delays, quality failures, urgent/critical language,
  complaints, recalls, rejections, or any language indicating something has gone wrong.
  Also escalate: ticket or support-system notifications where a comment implies the original
  question or issue is still unresolved — e.g. "Did your team get the answer they needed?",
  "Has this been resolved?", "Any update on this?", "Still waiting for a response", or similar
  follow-up language that signals an open, unanswered issue.
  Also escalate: operational delays where someone or something has been waiting with no resolution —
  e.g. driver/truck/shipment held up, not loaded, not dispatched, waiting since yesterday/hours ago,
  still not done. Also treat "please advise" as an escalation signal when paired with a described
  problem, as it indicates the sender is blocked and needs an immediate response.

- OTHER: Anything that does not require urgent attention.

Return raw JSON only, no markdown, no explanation:
{{
  "type": "ESCALATION or OTHER",
  "subtype": "general",
  "confidence": 0.0,
  "reason": "brief reason for classification"
}}

Email:
{email_text}
"""

    messages = [{"role": "user", "content": prompt}]
    for attempt in range(2):
        try:
            res = client.chat.completions.create(model="gpt-4o", messages=messages)
        except openai.OpenAIError as exc:
            logger.error("OpenAI API call failed (attempt %d/2): %s", attempt + 1, exc)
            raise
        content = strip_json_fences(res.choices[0].message.content.strip())
        try:
            result = json.loads(content)
            result["tokens"] = res.usage.total_tokens
            return result
        except json.JSONDecodeError:
            if attempt == 1:
                logger.error("GPT returned unparseable JSON: %s", content)
                raise
