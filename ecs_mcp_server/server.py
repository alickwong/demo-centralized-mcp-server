"""
CRM MCP Server — A simple MCP server that exposes CRM-like tools.
Deployed to ECS/Fargate as a Gateway target to demonstrate
AgentCore Gateway managing heterogeneous backends (Lambda + MCP servers).
"""

import json
from datetime import datetime

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

# --- Mock CRM Data ---

CONTACTS = [
    {"id": "C001", "name": "John Smith", "email": "john.smith@acme.com", "company": "Acme Corp", "role": "CTO"},
    {"id": "C002", "name": "Sarah Smith", "email": "sarah.smith@globex.com", "company": "Globex Inc", "role": "VP Engineering"},
    {"id": "C003", "name": "Alice Johnson", "email": "alice.j@initech.com", "company": "Initech", "role": "Director of IT"},
    {"id": "C004", "name": "Bob Williams", "email": "bob.w@umbrella.com", "company": "Umbrella Corp", "role": "Head of Security"},
    {"id": "C005", "name": "Emma Davis", "email": "emma.d@wayne.com", "company": "Wayne Enterprises", "role": "CFO"},
]

ACCOUNTS = {
    "A001": {
        "id": "A001",
        "name": "Acme Corp",
        "industry": "Manufacturing",
        "tier": "Enterprise",
        "arr": "$2.4M",
        "contacts": ["C001"],
        "last_activity": "2026-03-15",
    },
    "A002": {
        "id": "A002",
        "name": "Globex Inc",
        "industry": "Technology",
        "tier": "Mid-Market",
        "arr": "$450K",
        "contacts": ["C002"],
        "last_activity": "2026-03-18",
    },
    "A003": {
        "id": "A003",
        "name": "Initech",
        "industry": "Financial Services",
        "tier": "Enterprise",
        "arr": "$1.8M",
        "contacts": ["C003"],
        "last_activity": "2026-03-20",
    },
    "A004": {
        "id": "A004",
        "name": "Umbrella Corp",
        "industry": "Healthcare",
        "tier": "Strategic",
        "arr": "$5.2M",
        "contacts": ["C004"],
        "last_activity": "2026-03-19",
    },
    "A005": {
        "id": "A005",
        "name": "Wayne Enterprises",
        "industry": "Conglomerate",
        "tier": "Strategic",
        "arr": "$8.7M",
        "contacts": ["C005"],
        "last_activity": "2026-03-21",
    },
}

# --- MCP Server ---

mcp = FastMCP("CRM Server")


@mcp.tool()
def search_contacts(query: str) -> str:
    """Search CRM contacts by name, company, or role. Returns matching contacts."""
    query_lower = query.lower()
    matches = [
        c
        for c in CONTACTS
        if query_lower in c["name"].lower()
        or query_lower in c["company"].lower()
        or query_lower in c["role"].lower()
    ]
    if not matches:
        return json.dumps({"results": [], "message": f"No contacts found matching '{query}'"})
    return json.dumps({"results": matches, "count": len(matches)})


@mcp.tool()
def get_account_details(account_id: str) -> str:
    """Get detailed information about a CRM account by account ID (e.g., A001)."""
    account = ACCOUNTS.get(account_id)
    if not account:
        available = list(ACCOUNTS.keys())
        return json.dumps({"error": f"Account '{account_id}' not found. Available IDs: {available}"})
    return json.dumps(account)


@mcp.tool()
def list_accounts() -> str:
    """List all CRM accounts with summary information."""
    summaries = [
        {"id": a["id"], "name": a["name"], "industry": a["industry"], "tier": a["tier"], "arr": a["arr"]}
        for a in ACCOUNTS.values()
    ]
    return json.dumps({"accounts": summaries, "count": len(summaries)})


# --- FastAPI Health Check ---

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "crm-mcp-server", "timestamp": datetime.now().isoformat()}


# Mount MCP server on the FastAPI app using Streamable HTTP transport
# AgentCore Gateway connects via this endpoint
mcp_app = mcp.streamable_http_app()
app.mount("/mcp", mcp_app)
