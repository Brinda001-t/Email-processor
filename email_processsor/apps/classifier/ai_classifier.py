from openai import OpenAI
import os
import json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def classify_email(email_text):
    prompt = f"""
You are an email classifier for a supply chain system. Classify the email into one of these categories:

- COA: Email contains a Certificate of Analysis (quality report for materials/products).
  Look for: test results, lot number, manufacture date, expiration date, approved by,
  product specifications, quality test data, or subject containing "COA", "Certificate of Analysis".

- ESCALATION: Email contains an urgent issue, complaint, or problem requiring immediate attention.
  Look for: failed tests, wrong delivery, order delays, quality failures, urgent/critical language.

- OTHER: Anything that does not fit COA or ESCALATION.

Return raw JSON only, no markdown, no explanation:
{{
  "type": "COA or ESCALATION or OTHER",
  "reason": "brief reason for classification"
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