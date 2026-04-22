# Centralized MCP Server Management with AgentCore Gateway

Demonstrates **auth propagation** through MCP servers managed by **AWS AgentCore Gateway**, with two client paths:
- **Path 1 (Strands Agent):** Programmatic Okta ROPC flow with per-user Cedar policy enforcement
- **Path 2 (Claude Code):** Native MCP OAuth with browser-based Okta login and per-user Cedar policy enforcement

## Architecture

```
 User (CLI)
   |
   | username + password (Resource Owner Password grant)
   v
 Okta Token Endpoint ──> JWT (with groups, client_id claims)
   |
   v
 Strands Agent (JWT attached as Bearer token)
   |
   | MCP (StreamableHTTP + Bearer JWT)
   v
 AgentCore Gateway
   |── Ingress Auth: validates JWT (signature, audience, client_id)
   |── Cedar Policy Engine (ENFORCE mode)
   |     principal: AgentCore::OAuthUser::"<JWT sub>"
   |     action:    AgentCore::Action::"<TargetName>"
   |     resource:  AgentCore::Gateway::"<gateway-arn>"
   |     when:      context.input constraints (contextual control)
   |
   +-------------------+
   |                   |
   v                   v
 Lambda             Lambda
 (PolicyLookup)     (ClaimsData)
```

### Auth Flow

1. User authenticates via Okta Resource Owner Password grant -> receives JWT with `sub` claim
2. Strands Agent attaches JWT as `Bearer` token on MCP StreamableHTTP connection to Gateway
3. Gateway validates JWT (signature, audience, `client_id` claim) via Okta JWKS endpoint
4. Gateway maps JWT `sub` to Cedar principal `AgentCore::OAuthUser::"<sub>"`
5. Cedar policies evaluated in **ENFORCE** mode — Gateway permits or denies tool discovery and invocation
6. No access control logic needed in the agent or MCP servers

### Demo Scenario — Open Insurance

| User | Group | PolicyLookup | ClaimsData |
|------|-------|-------------|------------|
| Alice | `analysts` | ALLOWED | **BLOCKED** |
| Bob | `finance-admins` | ALLOWED | ALLOWED (full access) |
| Contextual user (`CONTEXTUAL_USER`) | — | ALLOWED | ALLOWED only when `max_amount <= CONTEXTUAL_MAX_AMOUNT` (Cedar contextual) |

Same Gateway, same agent code, same question. Different user identity -> different access.

### Cedar Contextual Control

Cedar's `when` clause constrains **tool input values**, not just tool access:

```cedar
permit(
    principal == AgentCore::OAuthUser::"<CONTEXTUAL_USER>",
    action == AgentCore::Action::"ClaimsData___query_claims",
    resource == AgentCore::Gateway::"<gateway-arn>"
)
when { context.input has "max_amount" && context.input.max_amount <= 100000 };
```

> **Note:** `<CONTEXTUAL_USER>` is set via the `CONTEXTUAL_USER` environment variable in `.env`. The Cedar policy and Lambda environment variables are configured dynamically from this value during setup.

This policy allows the contextual demo user to query claims, but the Gateway **denies** the call if:
- `max_amount` is not provided
- `max_amount > CONTEXTUAL_MAX_AMOUNT` (default: 100000)

Bob's policy has no `when` clause — full access with no constraints.

### Claude Code Auth Path (03_claude_code_oauth_demo.ipynb)

```
Claude Code
  |
  | MCP StreamableHTTP -> 401 -> OAuth discovery
  | Browser popup -> Okta login (Authorization Code + PKCE)
  | JWT Bearer token (cached automatically)
  v
AgentCore Gateway (CUSTOM_JWT authorizer)
  |-- Validates JWT (signature, audience, client_id)
  |-- Cedar Policy Engine (ENFORCE mode)
  |
  +-------------------+
  |                   |
  v                   v
Lambda             Lambda
(PolicyLookup)     (ClaimsData)
```

Claude Code has **native MCP OAuth** support. When connecting to the Gateway, it discovers
the Okta authorization server, opens a browser for login, and manages the JWT lifecycle
automatically. No token management code needed — Cedar policies enforce the same per-user
access control as the Strands agent path.

## Prerequisites

### 1. Okta Developer Account

Follow the complete setup guide at [`docs/okta-setup-guide.md`](docs/okta-setup-guide.md). The key steps are:

1. Create an **OIDC Web Application**
2. Enable **Resource Owner Password** grant type (via Okta API)
3. Create custom scopes (`groups`) and claims (`groups`, `client_id`) on the default authorization server
4. Create an access policy allowing the password grant
5. Create a password-only authentication policy (for OIE compatibility)
6. Create groups (`analysts`, `finance-admins`) and assign test users

> **Critical:** The `client_id` custom claim is required — AgentCore Gateway checks `allowedClients` against this claim, but Okta uses `cid` by default. See the setup guide for details.

### 2. AWS Account

- AWS CLI configured with appropriate credentials
- Permissions for: Lambda, ECS, ECR, IAM, Bedrock AgentCore, EC2 (VPC/SG)
- Docker installed (for building container images)

### 3. Python Environment

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

```bash
cp .env.example .env
# Edit .env with your Okta and AWS configuration
```

Required variables:

```env
OKTA_DOMAIN=your-domain.okta.com
OKTA_CLIENT_ID=your-client-id
OKTA_CLIENT_SECRET=your-client-secret
OKTA_API_TOKEN=your-api-token
AWS_REGION=ap-southeast-2
ALICE_USERNAME=alice@your-domain.okta.com
ALICE_PASSWORD=Testing123!
BOB_USERNAME=bob@your-domain.okta.com
BOB_PASSWORD=Testing123!
CONTEXTUAL_USER=your-contextual-user@your-domain.okta.com
CONTEXTUAL_MAX_AMOUNT=100000
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Fill in your Okta and AWS values

# 3. Run the setup notebook (creates all AWS resources)
jupyter notebook 01_setup.ipynb

# 4. Run the Strands agent demo (programmatic ROPC token flow)
jupyter notebook 02_demo.ipynb

# 5. Run the Claude Code demo (native OAuth with browser login)
jupyter notebook 03_claude_code_oauth_demo.ipynb

# 6. Cleanup (run the cleanup cells in each notebook when done)
```

## File Structure

```
centralized-mcp-server-demo/
├── README.md                    # This file
├── docs/
│   └── okta-setup-guide.md     # Complete Okta configuration guide
├── .env.example                 # Environment variable template
├── requirements.txt             # Python dependencies
├── 01_setup.ipynb               # Infrastructure setup notebook
├── 02_demo.ipynb                # Strands agent demo (Alice vs Bob)
├── 03_claude_code_oauth_demo.ipynb  # Claude Code demo (native OAuth)
├── terraform/                   # ECR, ECS, Lambda, IAM resources
│   ├── lambda.tf
│   ├── iam.tf
│   ├── ecs.tf
│   ├── ecr.tf
│   ├── networking.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   └── lambda/                  # Lambda function source code
│       ├── policy_lookup.py     # Insurance policy lookup (all users)
│       └── claims.py            # Claims data with max_amount filter (restricted)
├── ecs_mcp_server/              # CRM MCP server for ECS deployment
│   ├── server.py
│   ├── Dockerfile
│   └── requirements.txt
└── gateway_config.json          # Generated by setup notebook
```

## What Gets Created

The setup notebook creates these AWS resources:

| Resource | Purpose |
|----------|---------|
| 2 Lambda functions | PolicyLookup (unrestricted) + ClaimsData (restricted, supports `max_amount` filtering) |
| ECS/Fargate service | CRM MCP server container (for future HTTPS integration) |
| ECR repository | Docker image for the CRM MCP server |
| AgentCore Gateway | Centralized MCP proxy with Okta OIDC auth |
| Cedar policy engine | 3 policies in ENFORCE mode (all-users, Bob full, contextual user) |
| IAM roles | Lambda execution + ECS task execution + Gateway roles |

## Claims Data

The ClaimsData Lambda contains 5 insurance claims:

| Claim ID | Holder | Amount | Status |
|----------|--------|--------|--------|
| CLM-2024-0891 | Sarah Chen | $12,400 | Approved |
| CLM-2025-0023 | James Rodriguez | $45,000 | In Progress |
| CLM-2025-0067 | David Park | $89,500 | Under Investigation |
| CLM-2025-0112 | James Rodriguez | $185,000 | In Progress |
| CLM-2025-0134 | David Park | $250,000 | Under Review |

With `max_amount=100000`, only the first 3 claims are returned (all <= $100K).

## Known Limitations

### Cedar Entity Model

The Cedar schema for AgentCore Gateway uses:
- **Principal**: `AgentCore::OAuthUser::"<JWT sub>"` — the JWT `sub` claim is mapped to Cedar principals
- **Action**: `AgentCore::Action::"<TargetName>"` or `AgentCore::Action::"<Target>___<tool>"`
- **Resource**: `AgentCore::Gateway::"<gateway-arn>"`
- **Context**: `context.input` for tool input parameters (tool-level actions), `context.system` for target-level actions

JWT group claims (e.g., `groups`) are **not** exposed as Cedar principal attributes. Group-based filtering must use explicit principal matching per user `sub` value. Use `start_policy_generation` API to discover valid entity types for your gateway.

### MCP Server Targets Require HTTPS

The Gateway only accepts HTTPS endpoints for MCP server targets. The ECS-based CRM MCP server runs on HTTP, so it cannot be added as a Gateway target without an ALB with TLS termination.

## Cleanup

- Run the **Cleanup** cell at the bottom of `01_setup.ipynb` to delete all AWS resources (Gateway, Lambda, ECS, IAM)
- Run the **Cleanup** cell at the bottom of `03_claude_code_oauth_demo.ipynb` to remove the SPA app and revert the Gateway

## Key Concepts

- **AgentCore Gateway**: Managed MCP proxy that handles auth, routing, and Cedar policy enforcement
- **Custom JWT Authorizer**: Gateway validates Okta JWTs against the JWKS endpoint, checking `client_id`, audience, and signature
- **Cedar ENFORCE Mode**: Gateway evaluates Cedar policies at tool discovery and invocation time, mapping JWT `sub` to `AgentCore::OAuthUser` principals
- **Cedar Contextual Control**: `when` clause in Cedar policies constrains tool input values (e.g., `context.input.max_amount <= 100000`)
- **Auth Propagation**: User identity flows from Okta -> JWT -> Agent -> Gateway -> Cedar -> tools, with zero auth code in individual MCP servers
- **Native MCP OAuth**: Claude Code discovers the authorization server from Gateway metadata, handles browser-based login, and caches tokens — no custom auth code needed
