from openai import OpenAI
import os
import json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_coa_data(text):

    prompt = f"""
Extract the following fields from this Certificate of Analysis (COA) document and return as JSON only, no markdown.

Fields to extract:
- company
- address
- contact_phone
- contact_email
- product_name
- part_number
- lot_number
- lot_quantity
- manufacture_date
- expiration_date
- report_date
- approved_by
- test_results (list of objects, each with: test, specification, result, method)

Document:
{text}
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
    result = json.loads(content.strip())
    result["_tokens"] = res.usage.total_tokens
    return result