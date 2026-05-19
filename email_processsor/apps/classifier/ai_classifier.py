import json

from apps.core.openai_client import client, strip_json_fences

def classify_email(email_text):
    prompt = f"""
You are an email classifier for a supply chain system. Classify the email into one of these types:

- COA: Contains a Certificate of Analysis (quality report for materials/products).
  Look for: test results, lot number, manufacture date, expiration date, approved by,
  product specifications, quality test data, subject containing "COA", "Certificate of Analysis".

- ORDER: Contains an order inquiry, purchase order, or order status request.
  Look for: purchase order number, PO #, order confirmation, delivery status, order inquiry.
  Also extract the order number if present (e.g. TO1476530, PO-9821, ORD123). Check table
  headers like "Order Number", inline references, and any alphanumeric ID tied to the order.

- ESCALATION: Contains an urgent issue, complaint, or problem requiring immediate attention.
  Look for: failed tests, wrong delivery, order delays, quality failures, urgent/critical language.

- OTHER: Anything that does not fit the above categories.

Also pick the subtype:
- COA: "new" (first-time COA) or "amendment" (revised/updated COA for an existing lot)
- ORDER: "status_check" (checking existing order status), "driver_status" (asking about driver location, delivery ETA, or shipment tracking), or "new_order" (new purchase order)
- ESCALATION: "general" (any urgent issue, complaint, or problem requiring attention)
- OTHER: "spam" (unsolicited bulk email, no business value), "marketing" (promotional offers, advertisements, newsletters), or "general" (anything else)

Return raw JSON only, no markdown, no explanation:
{{
  "type": "COA or ORDER or ESCALATION or OTHER",
  "subtype": "new or amendment or status_check or driver_status or new_order or general",
  "order_numbers": ["list of all order/document IDs found in the email, or [] if none"],
  "confidence": 0.0,
  "reason": "brief reason for classification"
}}

Email:
{email_text}
"""

    messages = [{"role": "user", "content": prompt}]
    for attempt in range(2):
        res = client.chat.completions.create(model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", messages=messages)  # was "openai/gpt-4o"
        content = strip_json_fences(res.choices[0].message.content.strip())
        try:
            result = json.loads(content)
            result["tokens"] = res.usage.total_tokens
            return result
        except json.JSONDecodeError:
            if attempt == 1:
                raise
