from openai import OpenAI
import os
import json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def classify_email(email_text):
    prompt = f"""
Classify email into one of:
- COA
- ESCALATION
- OTHER

Return raw JSON only, no markdown, no explanation:
{{
  "type": "...",
  "reason": "..."
}}

Email:
{email_text}
"""

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    content = res.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())