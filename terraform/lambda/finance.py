import json

REVENUE_DATA = {
    "Q1_2026": {"quarter": "Q1 2026", "revenue": "$12.4M", "growth": "+18%", "top_segment": "Enterprise", "mrr": "$4.13M"},
    "Q4_2025": {"quarter": "Q4 2025", "revenue": "$10.8M", "growth": "+15%", "top_segment": "Mid-Market", "mrr": "$3.60M"},
    "Q3_2025": {"quarter": "Q3 2025", "revenue": "$9.4M", "growth": "+12%", "top_segment": "Enterprise", "mrr": "$3.13M"},
}

def lambda_handler(event, context):
    query = event.get("query", "").lower().strip()

    if "quarterly" in query or "revenue" in query or "all" in query:
        return {"statusCode": 200, "body": json.dumps({
            "data": list(REVENUE_DATA.values()),
            "summary": "Quarterly revenue data — CONFIDENTIAL"
        })}

    for key, data in REVENUE_DATA.items():
        if key.lower().replace("_", " ") in query or data["quarter"].lower() in query:
            return {"statusCode": 200, "body": json.dumps(data)}

    return {"statusCode": 200, "body": json.dumps({
        "available_periods": list(REVENUE_DATA.keys()),
        "hint": "Ask for quarterly revenue or a specific quarter like Q1 2026"
    })}
