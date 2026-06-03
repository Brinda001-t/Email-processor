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
  Also classify as OTHER if the email is a positive confirmation or resolution —
  e.g. "ready to ship", "already dispatched", "all set", "issue resolved",
  "confirmed", "thank you", "no problem", "looks good", "on its way".
  A reply that resolves or acknowledges a situation is NOT an escalation.
  Also classify as OTHER if the sender is already self-resolving the issue and
  not requesting action from the recipient — e.g. "I need to get with IT",
  "we are looking into it", "I will follow up", "working on it", "my apologies
  for the delay" as a courtesy note. An FYI update where no response is expected
  is NOT an escalation.
  Also classify as OTHER if the sender describes a problem but immediately provides
  an alternative plan or new ETA — e.g. "driver had a breakdown, we will send
  a different driver", "unable to load today, will deliver tomorrow". If the sender
  owns the resolution and gives a committed next step, no action is required from
  the recipient.

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
