import json

from apps.core.openai_client import client, strip_json_fences


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

    messages = [{"role": "user", "content": prompt}]
    for attempt in range(2):
        res = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
        content = strip_json_fences(res.choices[0].message.content.strip())
        try:
            result = json.loads(content)
            result["_tokens"] = res.usage.total_tokens
            return result
        except json.JSONDecodeError:
            if attempt == 1:
                raise