## Compute

# Build a centralized MCP server gateway with Amazon Bedrock AgentCore



Organizations building AI-powered applications with the Model Context Protocol (MCP) often deploy multiple MCP servers across their infrastructure. As the number of tools grows, managing authentication and authorization for each server becomes a significant operational challenge. Development teams find themselves embedding access control logic into individual backends, duplicating OAuth token validation across services, and struggling to maintain consistent security policies.

[Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) Gateway addresses this challenge by providing a managed MCP proxy that centralizes authentication, authorization, and tool routing in a single endpoint. With AgentCore Gateway, you can connect [AWS Lambda](https://aws.amazon.com/lambda/) functions as tool backends behind one gateway that enforces [Cedar](https://www.cedarpolicy.com/) policies for fine-grained access control.

In this post, we show you how to:

- Deploy Lambda functions as tool backends
- Create an AgentCore Gateway with OAuth-based JWT authentication through an external identity provider
- Define Cedar policies that control which users can discover and invoke specific tools
- Connect [Claude Code](https://docs.anthropic.com/en/docs/claude-code) to the gateway using native MCP OAuth support

We also highlight how [Azupay](https://azupay.com.au/), an Australian real-time payments company, is applying these patterns to secure AI agent access to enterprise payment tools at scale.

## Prerequisites

Before you begin, you need the following:

- An AWS account with permissions to create Lambda functions, IAM roles, and AgentCore resources
- [Terraform](https://www.terraform.io/) v1.5 or later installed
- An [Okta](https://www.okta.com/) developer account (or compatible OIDC provider) with an authorization server configured
- Python 3.12 or later with `boto3` and the AgentCore SDK installed
- Claude Code installed on your local machine

## Solution overview

The solution consists of three layers: tool backends, a managed gateway, and AI agent clients.

The following diagram illustrates the architecture:

```
┌──────────────────────────────┐
│     AI Agent Clients         │
│  (Claude Code, custom apps)  │
│  OAuth token in each request │
└─────────────┬────────────────┘
              │ MCP Streamable HTTP + JWT
              ▼
┌──────────────────────────────┐
│  AgentCore Gateway           │
│  ┌────────────────────────┐  │
│  │ JWT Validation (Okta)  │  │
│  │ Cedar Policy Engine    │  │
│  │ Tool Discovery Filter  │  │
│  │ Request Routing        │  │
│  └────────────────────────┘  │
└──┬──────────────────────┬────┘
   ▼                      ▼
┌────────────────┐ ┌────────────────┐
│ Lambda         │ │ Lambda         │
│ PolicyLookup   │ │ ClaimsData     │
└────────────────┘ └────────────────┘
```

The preceding figure illustrates the following workflow:

1. An AI agent client sends an MCP request to the AgentCore Gateway with a JWT bearer token
2. The gateway validates the JWT signature against the identity provider's JWKS endpoint
3. The Cedar policy engine evaluates whether the authenticated user is permitted to discover or invoke the requested tool
4. If permitted, the gateway routes the request to the appropriate Lambda function target
5. The Lambda function processes the request and returns results through the gateway to the client

The key benefit of this architecture is that individual backends contain zero access control logic. Authentication and authorization are handled entirely at the gateway layer through Cedar policies.

## Step 1: Deploy the tool backends with Terraform

The demo uses two Lambda function targets to represent a realistic enterprise scenario: an insurance policy lookup service and a claims data service with confidential records.

### Define the Lambda functions

The PolicyLookup Lambda function serves as a read-only policy database. Create the handler in `terraform/lambda/policy_lookup.py`:

```python
# Policy lookup handler - returns insurance policy details
def lambda_handler(event, context):
    policy_number = event.get("policy_number", "")
    
    policies = {
        "POL-10042": {
            "holder": "Sarah Chen",
            "type": "Homeowners",
            "coverage_limit": 750000,
            "status": "Active"
        },
        # Additional policies defined here
    }
    
    if policy_number in policies:
        return {"status": "found", "policy": policies[policy_number]}
    return {"status": "not_found", "message": f"No policy found for {policy_number}"}
```

The ClaimsData Lambda function handles confidential claims records and supports contextual filtering based on the calling user's identity:

```python
# Claims data handler - supports query filtering and user-based restrictions
def lambda_handler(event, context):
    query = event.get("query", "")
    max_amount = event.get("max_amount", None)
    
    # Read the caller's identity from the gateway context
    request_context = event.get("context", {}).get("requestContext", {})
    caller_sub = request_context.get("sub", "")
    
    # Apply per-user amount limits when configured
    contextual_user = os.environ.get("CONTEXTUAL_USER", "")
    if caller_sub == contextual_user and max_amount:
        contextual_limit = int(os.environ.get("CONTEXTUAL_MAX_AMOUNT", "100000"))
        claims = [c for c in claims if c["amount_claimed"] <= contextual_limit]
    
    return {"status": "success", "claims": matching_claims}
```

### Define the Terraform resources

The `terraform/lambda.tf` file packages and deploys both Lambda functions:

```hcl
# Package Lambda source code
data "archive_file" "policy_lookup_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/policy_lookup.py"
  output_path = "${path.module}/.build/policy_lookup.zip"
}

resource "aws_lambda_function" "policy_lookup" {
  function_name    = "${var.demo_prefix}-policy-lookup"
  handler          = "policy_lookup.lambda_handler"
  runtime          = "python3.12"
  role             = aws_iam_role.lambda_role.arn
  filename         = data.archive_file.policy_lookup_zip.output_path
  source_code_hash = data.archive_file.policy_lookup_zip.output_base64sha256
}
```

### Build and deploy

Run the following commands to deploy the infrastructure:

```bash
# Initialize and apply Terraform
cd terraform
terraform init
terraform apply
```

After the deployment completes, Terraform outputs the Lambda function ARNs that you need for the gateway configuration.

## Step 2: Create the AgentCore Gateway

The AgentCore Gateway acts as the centralized MCP proxy. You create the gateway, configure JWT authentication, and register each backend as a target.

### Configure the JWT authorizer

The gateway uses a `CUSTOM_JWT` authorizer that validates tokens issued by your Okta authorization server:

```python
import boto3

agentcore_client = boto3.client("bedrock-agentcore", region_name="us-east-1")

# Create the gateway with Okta JWT validation
response = agentcore_client.create_gateway(
    name="mcp-demo-gateway",
    protocolType="MCP",
    authorizerType="CUSTOM_JWT",
    authorizerConfiguration={
        "customJWTConfiguration": {
            "issuer": "https://your-domain.okta.com/oauth2/default",
            "audiences": ["api://default"],
            "allowedClients": ["<your-okta-client-id>"],
            "jwksUri": "https://your-domain.okta.com/oauth2/default/v1/keys"
        }
    }
)

gateway_id = response["gatewayId"]
```

When a request arrives, the gateway validates the JWT signature against the Okta JWKS endpoint, checks the audience and client ID claims, and maps the `sub` claim to a Cedar principal of type `AgentCore::OAuthUser`.

### Register backend targets

Each backend is registered as a named target on the gateway:

```python
# Register the PolicyLookup Lambda as a target
agentcore_client.create_gateway_target(
    gatewayIdentifier=gateway_id,
    name="PolicyLookup",
    targetConfiguration={
        "lambdaTargetConfiguration": {
            "lambdaArn": "<policy-lookup-lambda-arn>"
        }
    }
)

# Register the ClaimsData Lambda as a target
agentcore_client.create_gateway_target(
    gatewayIdentifier=gateway_id,
    name="ClaimsData",
    targetConfiguration={
        "lambdaTargetConfiguration": {
            "lambdaArn": "<claims-data-lambda-arn>"
        }
    }
)
```

Lambda targets receive invocations directly through the gateway's IAM role. The gateway translates MCP tool calls into Lambda invocations and returns the results to the client.

## Step 3: Define Cedar policies for access control

Cedar policies determine which users can discover and invoke which tools. The gateway evaluates these policies in **ENFORCE** mode, meaning that requests without a matching permit policy are denied.

### Create the policy engine

Attach a Cedar policy engine to the gateway:

```python
# Create and attach the policy engine
policy_engine = agentcore_client.create_gateway_policy_engine(
    gatewayIdentifier=gateway_id,
    policyEngineConfiguration={
        "cedarPolicyEngineConfiguration": {
            "enforcementMode": "ENFORCE"
        }
    }
)
```

### Define access policies

The following examples demonstrate three common authorization patterns.

**Pattern 1, open access for a specific target.** Allow authenticated users to discover and call the PolicyLookup tool:

```cedar
permit(
    principal is AgentCore::OAuthUser,
    action in [
        AgentCore::Action::"PolicyLookup",
        AgentCore::Action::"PolicyLookup___lookup_policy"
    ],
    resource == AgentCore::Gateway::"<gateway-arn>"
);
```

This policy uses `principal is AgentCore::OAuthUser` (without a specific identifier), which matches authenticated users who hold a valid JWT.

**Pattern 2, role-based access for sensitive data.** Restrict the ClaimsData target to a specific user:

```cedar
permit(
    principal == AgentCore::OAuthUser::"bob@example.com",
    action in [
        AgentCore::Action::"ClaimsData",
        AgentCore::Action::"ClaimsData___query_claims"
    ],
    resource == AgentCore::Gateway::"<gateway-arn>"
);
```

With this policy, only Bob can see and invoke the ClaimsData tool. Other authenticated users do not see this tool in the tool discovery response. The gateway filters it from the tool list entirely.

**Pattern 3, contextual constraints on tool inputs.** Restrict a user's queries to claims below a specific dollar amount:

```cedar
permit(
    principal == AgentCore::OAuthUser::"alice@example.com",
    action == AgentCore::Action::"ClaimsData___query_claims",
    resource == AgentCore::Gateway::"<gateway-arn>"
)
when {
    context.input has "max_amount" &&
    context.input.max_amount <= 100000
};
```

The `when` clause inspects the tool's input parameters at invocation time. If Alice calls `query_claims` with a `max_amount` value exceeding 100,000, the gateway denies the request before it reaches the Lambda function.

### Cedar entity model

The following table describes how the gateway maps JWT claims and MCP concepts to Cedar entities:

| Cedar Entity | Maps From | Example |
|---|---|---|
| Principal | JWT `sub` claim | `AgentCore::OAuthUser::"bob@example.com"` |
| Action (target) | Gateway target name | `AgentCore::Action::"PolicyLookup"` |
| Action (tool) | Target + tool name | `AgentCore::Action::"PolicyLookup___lookup_policy"` |
| Resource | Gateway ARN | `AgentCore::Gateway::"arn:aws:bedrock-agentcore:..."` |
| Context | Tool input parameters | `context.input.max_amount` |

Target-level actions control tool discovery (whether the tool appears in the list). Tool-level actions control invocation (whether the tool can be called with specific inputs).

## Step 4: Connect Claude Code to the gateway

Claude Code supports native MCP OAuth, which means it can authenticate with the AgentCore Gateway using the Authorization Code flow with PKCE, with no custom token management required.

### Create an Okta SPA application

Claude Code runs in the browser context, so you need a public client (Single Page Application) in Okta:

```python
import requests

# Create SPA application in Okta
spa_app = requests.post(
    "https://your-domain.okta.com/api/v1/apps",
    headers={"Authorization": f"SSWS {okta_api_token}"},
    json={
        "name": "oidc_client",
        "label": "Claude Code MCP Gateway",
        "signOnMode": "OPENID_CONNECT",
        "settings": {
            "oauthClient": {
                "application_type": "browser",
                "grant_types": ["authorization_code"],
                "redirect_uris": ["http://localhost:8400/callback"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none"
            }
        }
    }
)

spa_client_id = spa_app.json()["credentials"]["oauthClient"]["client_id"]
```

After creating the SPA application, add its client ID to the gateway's `allowedClients` list:

```python
# Update gateway to accept tokens from the SPA app
agentcore_client.update_gateway(
    gatewayIdentifier=gateway_id,
    authorizerConfiguration={
        "customJWTConfiguration": {
            "allowedClients": [existing_client_id, spa_client_id]
        }
    }
)
```

### Configure Claude Code

Add the AgentCore Gateway as an MCP server in Claude Code. You can use the `claude mcp add-json` command:

```bash
claude mcp add-json "agentcore-gateway" '{
  "type": "http",
  "url": "https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp",
  "oauth": {
    "clientId": "<spa-client-id>",
    "callbackPort": 8400,
    "scope": "openid groups",
    "authorizationUrl": "https://your-domain.okta.com/oauth2/default/v1/authorize",
    "tokenUrl": "https://your-domain.okta.com/oauth2/default/v1/token"
  }
}'
```

When Claude Code connects to the gateway, the following flow occurs:

1. Claude Code sends an initial MCP request to the gateway endpoint
2. The gateway returns a 401 response with OAuth discovery metadata
3. Claude Code opens a browser window to the Okta login page
4. After you authenticate, Okta issues an authorization code
5. Claude Code exchanges the code for a JWT using PKCE (no client secret required)
6. The JWT is cached locally in `~/.claude/oauth-tokens/` for subsequent requests
7. Claude Code resends the MCP request with the JWT as a bearer token
8. The gateway validates the token and returns the filtered tool list based on your Cedar policies

### Verify the connection

After authentication, Claude Code displays the tools available to you based on your Cedar policies. For example, a user with the finance-admin role sees both PolicyLookup and ClaimsData tools, while an analyst-role user sees only PolicyLookup.

You can test the connection by asking Claude Code to look up an insurance policy:

```
> Look up policy POL-10042 for Sarah Chen

Claude Code calls the lookup_policy tool via the AgentCore Gateway
and returns the policy details: Homeowners coverage, $750,000 limit, Active status.
```

## Customer story: Azupay — Securing real-time payment tools with centralized access control

[Azupay](https://azupay.com.au/) is an Australian fintech company pioneering real-time Pay by Bank solutions for enterprise. Founded in 2019, Azupay was the first to offer consumer-to-business and business-to-business payment solutions using PayID and [PayTo](https://payto.com.au/) on Australia's [New Payments Platform (NPP)](https://www.nppa.com.au/). The company serves major customers across banking, telecommunications, education, and government, including Optus, which processed over 450,000 PayID transactions from 88,000+ customers in its first 12 months of using Azupay.

Azupay's co-founder and CTO, Andrew Seymour, was the lead architect for xxxxxxxxx

**The challenge:** As Azupay's platform scales to handle growing real-time payment volumes across enterprises, the engineering team needs to give internal developers and operations staff AI-powered access to xxxxxxxxxx

**The solution:** 


**Outcomes:** 

> "Working with Azupay has allowed us to modernise the way Australian universities handle payments. The ability to offer PayID and PayTo in a real-time, fully reconciled way is a game-changer for institutions and students alike."
> — Azupay customer testimonial

## Cleanup

To avoid ongoing charges, delete the resources in reverse order:

1. Delete the Cedar policies and policy engine from the AgentCore Gateway
2. Delete the gateway targets and the gateway itself
3. Run `terraform destroy` to remove the Lambda functions and IAM roles
4. Delete the Okta SPA application if you created one for Claude Code
5. Remove the MCP server configuration from Claude Code: `claude mcp remove agentcore-gateway`

## Conclusion

In this post, we showed you how to build a centralized MCP server gateway using Amazon Bedrock AgentCore that unifies authentication and authorization across multiple tool backends. As demonstrated by Azupay's real-time payment use case, this architecture applies wherever organizations need to give AI agents secure, governed access to enterprise tools.

Key takeaways:

- **Centralize access control at the gateway layer.** By moving authentication and authorization out of individual backends, you reduce code duplication and create a single point of policy enforcement. Backend services can focus on business logic with zero access control code.
- **Use Cedar policies for fine-grained tool access.** Cedar's principal-action-resource model maps naturally to the MCP tool discovery and invocation flow. You can control which users see which tools, and constrain tool inputs with `when` clauses for contextual authorization.
- **Connect AI coding assistants with native OAuth.** Claude Code's built-in MCP OAuth support enables browser-based PKCE authentication flows without custom token management. This provides a production-ready pattern for connecting AI agents to protected enterprise tools.
- **Use Lambda functions as serverless tool backends.** AgentCore Gateway invokes Lambda functions on your behalf, so you can build lightweight, serverless tools without managing infrastructure or exposing public endpoints.

Get started by exploring the following resources:

- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/) product page
- [AgentCore Gateway documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [Cedar policy language reference](https://docs.cedarpolicy.com/)
- [Claude Code MCP documentation](https://docs.anthropic.com/en/docs/claude-code/mcp)
- [Demo repository on GitHub](https://github.com/your-org/demo-centralized-mcp-server)

For more information about MCP server patterns on AWS, refer to the [AgentCore Getting Started Guide](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-getting-started.html).

---

### About the authors
**Andrew Seymour** Azupay's co-founder and CTO 

**Alick Wong** is a Solutions Architect at Amazon Web Services, focusing on AI/ML and serverless architectures. [Author Name] helps customers design and implement production-ready AI agent systems on AWS.
