from openai import OpenAI
import os
import json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_escalation_data(text):
    prompt = f"""
Extract the following fields from this escalation or complaint email and return as JSON only, no markdown.

Fields:
- affected_product: the product or material being complained about (empty string if not mentioned)
- order_number: any PO or order number referenced (empty string if not mentioned)
- complaint_type: short label for the complaint category, choose the best fit from:
  "wrong delivery", "quality failure", "late shipment", "damaged goods",
  "missing items", "billing dispute", "documentation issue", "other"

Email:
{text}
"""
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    content = res.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content.strip())
