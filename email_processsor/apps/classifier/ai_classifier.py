import json

from apps.core.openai_client import client, strip_json_fences

def classify_email(email_text):
    prompt = f"""
You are an email classifier. Classify the email as ESCALATION or OTHER.

- ESCALATION: Contains an urgent issue, complaint, or problem requiring immediate attention.
  Look for: failed tests, wrong delivery, order delays, quality failures, urgent/critical language,
  complaints, recalls, rejections, or any language indicating something has gone wrong.

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
        res = client.chat.completions.create(model="gpt-4o", messages=messages)
        content = strip_json_fences(res.choices[0].message.content.strip())
        try:
            result = json.loads(content)
            result["tokens"] = res.usage.total_tokens
            return result
        except json.JSONDecodeError:
            if attempt == 1:
                raise
