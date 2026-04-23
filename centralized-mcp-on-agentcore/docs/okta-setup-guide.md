# Okta OIDC Setup Guide for Claude Code with Bedrock

This guide documents the steps to configure Okta as an OIDC identity provider for the Centralized MCP Server demo, used with Claude Code and Amazon Bedrock.

## Prerequisites

- An Okta account (free trial or developer edition)
- Access to the Okta Admin Console

## Step 1: Log in to Okta Admin Console

1. Navigate to [https://login.okta.com](https://login.okta.com)
2. Enter your company name (Okta subdomain), e.g. `dev-XXXXXXXX`
3. Sign in with your admin credentials
4. You will land on the **Admin Console** dashboard

## Step 2: Create a New App Integration

1. In the left sidebar, click **Applications** > **Applications**
2. Click **Create App Integration**
3. In the dialog that appears, configure:
   - **Sign-in method**: Select **OIDC - OpenID Connect**
   - **Application type**: Select **Web Application**
4. Click **Next**

## Step 3: Configure the App Integration

On the **New Web App Integration** form, fill in the following:

### General Settings

| Field | Value |
|---|---|
| **App integration name** | `Claude Code Bedrock` |

### Proof of Possession

Leave **unchecked** — DPoP is not required.

### Grant Type

| Grant | Enabled |
|---|---|
| Client Credentials | No |
| Authorization Code | Yes (required, cannot be unchecked) |
| Refresh Token | Yes (check this) |

### Sign-in Redirect URIs

```
http://localhost:8080/authorization-code/callback
```

This is Okta's default redirect URI for web apps. Claude Code's local auth server will listen on this endpoint.

### Sign-out Redirect URIs

```
http://localhost:8080
```

Leave as default.

### Trusted Origins / Base URIs

Leave empty (optional).

### Assignments — Controlled Access

Select **Allow everyone in your organization to access**.

This ensures all users in your Okta org can authenticate with Claude Code.

### Save

Click **Save** to create the application.

## Step 4: Retrieve Client Credentials

After saving, you will be redirected to the app's **General** tab. Note the following values:

| Field | Description |
|---|---|
| **Client ID** | Shown under Client Credentials (e.g. `0oaXXXXXXXXXXXXXXXXXX`) |
| **Client Secret** | Shown below the Client ID. **Save this immediately** — Okta only displays it once. If lost, click "Generate new secret" to create a replacement. |

### Client Authentication

The app is configured with **Client secret** authentication (not public key/private key).

## Step 5: Update .env File

Update the `.env` file in the project root with the values from Okta:

```env
# Okta OIDC Configuration
OKTA_DOMAIN=dev-XXXXXXXX.okta.com
OKTA_CLIENT_ID=0oaXXXXXXXXXXXXXXXXXX
OKTA_CLIENT_SECRET=<your-client-secret>
```

> **Important:** Use the non-admin domain (e.g., `dev-XXXXXXXX.okta.com`), not the admin console domain (`dev-XXXXXXXX-admin.okta.com`). The admin domain does not serve API requests and will cause all subsequent API calls to fail.

## OIDC Endpoints Reference

> **Important:** This demo uses the **default authorization server** (`/oauth2/default`), not the Org server. The Org server does not support custom scopes or claims.

| Endpoint | URL |
|---|---|
| **Issuer** | `https://dev-XXXXXXXX.okta.com/oauth2/default` |
| **OpenID Config** | `https://dev-XXXXXXXX.okta.com/oauth2/default/.well-known/openid-configuration` |
| **Authorization** | `https://dev-XXXXXXXX.okta.com/oauth2/default/v1/authorize` |
| **Token** | `https://dev-XXXXXXXX.okta.com/oauth2/default/v1/token` |
| **JWKS** | `https://dev-XXXXXXXX.okta.com/oauth2/default/v1/keys` |

## Step 6: Create an Okta API Token

An API token is needed for server-side Okta management operations (e.g., creating users, managing groups programmatically).

1. In the Okta Admin Console, go to **Security** > **API**
2. Click the **Tokens** tab
3. Click **Create Token**
4. Enter a name for the token, e.g. `Centralized MCP Server Setup`
5. Click **Create Token**
6. **Copy the token value immediately** — Okta only displays it once. If lost, you must revoke and create a new one.

Add the token to your `.env` file:

```env
OKTA_API_TOKEN=<your-api-token>
```

> **Note:** API tokens inherit the permissions of the admin who creates them. Use a Super Admin account for full access, or a scoped admin for least-privilege. Tokens expire if unused for 30 days, and are revoked if the creating admin's account is deactivated.

## Step 7: Enable Resource Owner Password Grant

Okta Identity Engine (OIE) trial accounts don't expose the Resource Owner Password (ROPC) grant type in the UI. You must enable it via the Okta Management API.

```bash
# Get the full current app config (Okta PUT requires the complete app object)
APP_CONFIG=$(curl -s -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  https://${OKTA_DOMAIN}/api/v1/apps/${OKTA_CLIENT_ID})

echo "$APP_CONFIG" | jq '.settings.oauthClient.grant_types'

# Merge new grant_types into the full app config, then PUT it back
UPDATED_APP=$(echo "$APP_CONFIG" | jq '.settings.oauthClient.grant_types = ["authorization_code", "refresh_token", "password", "client_credentials"]')

curl -s -X PUT -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/apps/${OKTA_CLIENT_ID} \
  -d "$UPDATED_APP" | jq '.settings.oauthClient.grant_types'
```

> **Gotcha:** The Okta Apps API requires the full app object on PUT. Sending only the `settings` fragment will fail with `Api validation failed: label`. Always GET the full config first, modify the field you need, then PUT the whole object back.

**Expected result:** `grant_types` now includes `password`.

## Step 8: Create Custom Scopes on the Default Authorization Server

The demo needs a `groups` scope to include group memberships in access tokens.

```bash
# Create 'groups' scope
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/scopes \
  -d '{
    "name": "groups",
    "description": "Access to user groups",
    "consent": "IMPLICIT"
  }'
```

## Step 9: Create Custom Claims on the Default Authorization Server

Two custom claims are required on access tokens:

### `groups` claim — includes user's group memberships

```bash
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/claims \
  -d '{
    "name": "groups",
    "status": "ACTIVE",
    "claimType": "RESOURCE",
    "valueType": "GROUPS",
    "value": ".*",
    "group_filter_type": "REGEX",
    "alwaysIncludeInToken": true,
    "conditions": { "scopes": ["groups"] }
  }'
```

> **Note:** The `group_filter_type` field is required when `valueType` is `GROUPS`. Without it, the API returns `Api validation failed: group_filter_type`. Use `"REGEX"` to match the `".*"` value pattern.

### `client_id` claim — required for AgentCore Gateway

> **Important:** AgentCore Gateway checks `allowedClients` against the `client_id` claim in the JWT. Okta puts the client ID in the non-standard `cid` claim by default. Without this custom claim, the Gateway returns `401 insufficient_scope`.

```bash
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/claims \
  -d '{
    "name": "client_id",
    "status": "ACTIVE",
    "claimType": "RESOURCE",
    "valueType": "EXPRESSION",
    "value": "app.clientId",
    "alwaysIncludeInToken": true,
    "conditions": { "scopes": [] }
  }'
```

## Step 10: Create an Access Policy on the Authorization Server

The default authorization server needs a policy that allows the password grant type.

```bash
# Create access policy
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/policies \
  -d '{
    "name": "Demo App Policy",
    "description": "Allow password grant for demo app",
    "type": "OAUTH_AUTHORIZATION_POLICY",
    "status": "ACTIVE",
    "priority": 1,
    "conditions": {
      "clients": { "include": ["ALL_CLIENTS"] }
    }
  }'
```

Note the policy `id` from the response, then create a rule:

```bash
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/policies/${POLICY_ID}/rules \
  -d '{
    "name": "Allow all grant types",
    "type": "RESOURCE_ACCESS",
    "status": "ACTIVE",
    "priority": 1,
    "conditions": {
      "grantTypes": {
        "include": ["implicit", "password", "client_credentials", "authorization_code"]
      },
      "people": {
        "groups": {
          "include": ["EVERYONE"]
        }
      },
      "scopes": {
        "include": ["*"]
      }
    },
    "actions": {
      "token": {
        "accessTokenLifetimeMinutes": 60,
        "refreshTokenLifetimeMinutes": 0,
        "refreshTokenWindowMinutes": 10080
      }
    }
  }'
```

> **Gotcha:** The `people` condition must use `"groups": { "include": ["EVERYONE"] }`, not `"everyone": { "include": ["EVERYONE"] }`. The latter structure is not recognized by the API and results in a validation error requiring at least one valid user or group.

## Step 11: Create a Password-Only Authentication Policy

Okta OIE defaults to multi-factor authentication, which blocks the Resource Owner Password flow. Create a 1FA policy for the demo app.

```bash
# Create authentication policy
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/policies \
  -d '{
    "name": "Password Only (Demo)",
    "description": "1FA password-only policy for ROPC demo flow",
    "type": "ACCESS_POLICY",
    "status": "ACTIVE"
  }'
```

Note the policy `id`, then create a rule:

```bash
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/policies/${POLICY_ID}/rules \
  -d '{
    "name": "Password only",
    "type": "ACCESS_POLICY",
    "status": "ACTIVE",
    "priority": 1,
    "conditions": {
      "network": { "connection": "ANYWHERE" }
    },
    "actions": {
      "appSignOn": {
        "access": "ALLOW",
        "verificationMethod": {
          "factorMode": "1FA",
          "type": "ASSURANCE",
          "reauthenticateIn": "PT43800H",
          "constraints": [
            { "knowledge": { "types": ["password"] } }
          ]
        }
      }
    }
  }'
```

> **Gotcha:** The rule `type` must be `"ACCESS_POLICY"` (matching the parent policy type), not `"ACCESS_POLICY_RULE"`. Using the wrong type returns `Invalid rule type specified`.
>
> **Note:** The new policy is created with a default "Catch-all Rule" set to 2FA. Adding a higher-priority rule (priority 1) with 1FA overrides it for all matching requests. You do not need to modify the catch-all rule (it's read-only).

Then assign this policy to your app:

```bash
curl -X PUT -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/apps/${OKTA_CLIENT_ID}/policies/${POLICY_ID}
```

## Step 12: Create Demo Users and Groups

### Create groups

```bash
# Create 'analysts' group
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/groups \
  -d '{ "profile": { "name": "analysts", "description": "Analyst group" } }'

# Create 'finance-admins' group
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/groups \
  -d '{ "profile": { "name": "finance-admins", "description": "Finance administrators" } }'
```

### Create users

Create users via the Okta Admin Console (**Directory** > **People** > **Add Person**), or via the API:

```bash
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/users?activate=true \
  -d '{
    "profile": {
      "firstName": "Alice",
      "lastName": "Demo",
      "email": "alice@your-domain.okta.com",
      "login": "alice@your-domain.okta.com"
    },
    "credentials": {
      "password": { "value": "Testing123!" }
    }
  }'
```

Repeat for Bob. Note each user's `id` from the response.

### Assign users to groups

```bash
# Alice -> analysts
curl -X PUT -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  https://${OKTA_DOMAIN}/api/v1/groups/${ANALYSTS_GROUP_ID}/users/${ALICE_USER_ID}

# Bob -> finance-admins
curl -X PUT -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  https://${OKTA_DOMAIN}/api/v1/groups/${FINANCE_ADMINS_GROUP_ID}/users/${BOB_USER_ID}
```

### Update .env with user credentials

```env
ALICE_USERNAME=alice@your-domain.okta.com
ALICE_PASSWORD=Testing123!
BOB_USERNAME=bob@your-domain.okta.com
BOB_PASSWORD=Testing123!
```

## Step 13: Verify Token Configuration

Test that tokens contain the expected claims:

```bash
# Get an access token for Alice
TOKEN_RESPONSE=$(curl -s -X POST \
  https://${OKTA_DOMAIN}/oauth2/default/v1/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password&username=${ALICE_USERNAME}&password=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${ALICE_PASSWORD}'))")&scope=openid+profile+groups&client_id=${OKTA_CLIENT_ID}&client_secret=${OKTA_CLIENT_SECRET}")

# Check for errors
echo "$TOKEN_RESPONSE" | jq -e '.error' > /dev/null 2>&1 && echo "ERROR:" && echo "$TOKEN_RESPONSE" | jq . && exit 1

TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token')

# Decode and verify claims (add base64 padding for macOS compatibility)
PAYLOAD=$(echo "$TOKEN" | cut -d. -f2 | tr '_-' '/+')
PADDING=$(( 4 - ${#PAYLOAD} % 4 ))
[ $PADDING -lt 4 ] && PAYLOAD="${PAYLOAD}$(printf '=%.0s' $(seq 1 $PADDING))"
echo "$PAYLOAD" | base64 -d 2>/dev/null | jq .
```

> **Note:** The password must be URL-encoded in the request body. Special characters like `!` will cause the request to fail silently or return `invalid_grant` if not encoded. The example above uses Python for encoding; alternatively, manually replace `!` with `%21`.
>
> **macOS note:** The `base64 -d` command on macOS may fail on JWT payloads because they use base64url encoding (no padding). The decode snippet above handles this by converting base64url characters and adding padding.

**Expected claims in the access token:**

| Claim | Expected Value |
|-------|----------------|
| `aud` | `api://default` |
| `iss` | `https://{domain}/oauth2/default` |
| `cid` | Your client ID |
| `client_id` | Your client ID (custom claim) |
| `scp` | `["openid", "profile", "groups"]` |
| `groups` | `["analysts", "Everyone"]` for Alice |
| `sub` | User's login email |

## OIDC Endpoints Reference (Default Authorization Server)

All endpoints use the **default** authorization server at `/oauth2/default`:

| Endpoint | URL |
|---|---|
| **OIDC Issuer** | `https://{domain}/oauth2/default` |
| **OpenID Config** | `https://{domain}/oauth2/default/.well-known/openid-configuration` |
| **Authorization** | `https://{domain}/oauth2/default/v1/authorize` |
| **Token** | `https://{domain}/oauth2/default/v1/token` |
| **JWKS** | `https://{domain}/oauth2/default/v1/keys` |

> **Note:** The demo uses the `/oauth2/default` authorization server, not the Org authorization server at the root path. This is important — the Org server does not support custom scopes or claims.

## Troubleshooting

### `Api validation failed: label` when updating app grant types
The Okta Apps API requires the full app object on PUT requests. You cannot send a partial payload with only the fields you want to change. See [Step 7](#step-7-enable-resource-owner-password-grant) for the correct approach (GET full config → modify → PUT back).

### `Api validation failed: group_filter_type` when creating groups claim
The `group_filter_type` field is required when creating a claim with `valueType: "GROUPS"`. Add `"group_filter_type": "REGEX"` to the request body. See [Step 9](#step-9-create-custom-claims-on-the-default-authorization-server).

### `Invalid rule type specified` when creating authentication policy rule
The rule `type` must match the parent policy type. For `ACCESS_POLICY` policies, use `"type": "ACCESS_POLICY"` (not `"ACCESS_POLICY_RULE"`). See [Step 11](#step-11-create-a-password-only-authentication-policy).

### `conditions.people: At least one of ... must contain a valid user or group`
The `people` condition in authorization server policy rules must use `"groups": { "include": ["EVERYONE"] }`, not `"everyone": { "include": ["EVERYONE"] }`. See [Step 10](#step-10-create-an-access-policy-on-the-authorization-server).

### `insufficient_scope` from AgentCore Gateway
The Gateway checks the `client_id` claim (not `cid`). Ensure you created the custom `client_id` claim in [Step 9](#step-9-create-custom-claims-on-the-default-authorization-server).

### `unauthorized_client: The client is not authorized to use the provided grant type`
The `password` grant type isn't enabled on the app. Follow [Step 7](#step-7-enable-resource-owner-password-grant).

### `invalid_scope: One or more scopes are not configured`
The `groups` scope hasn't been created on the default authorization server. Follow [Step 8](#step-8-create-custom-scopes-on-the-default-authorization-server).

### `access_denied: Policy evaluation failed`
No access policy on the authorization server allows the password grant. Follow [Step 10](#step-10-create-an-access-policy-on-the-authorization-server).

### `Resource owner password credentials authentication denied by sign on policy`
The app's authentication policy requires 2FA. Create and assign a password-only policy per [Step 11](#step-11-create-a-password-only-authentication-policy).

### `PASSWORD_EXPIRED` on login
Reset the user's password via the Okta API:

```bash
# Initiate authentication
AUTH=$(curl -s -X POST https://${OKTA_DOMAIN}/api/v1/authn \
  -H "Content-Type: application/json" \
  -d '{"username": "alice@your-domain.okta.com", "password": "OldPassword"}')

STATE_TOKEN=$(echo $AUTH | jq -r '.stateToken')

# Change password
curl -X POST https://${OKTA_DOMAIN}/api/v1/authn/credentials/change_password \
  -H "Content-Type: application/json" \
  -d "{\"stateToken\": \"${STATE_TOKEN}\", \"oldPassword\": \"OldPassword\", \"newPassword\": \"NewPassword!\"}"
```

### "Client secret" not visible
If you navigate away before saving the client secret, generate a new one:
1. Go to the app's **General** tab
2. Under Client Credentials, click **Edit**
3. Click **Generate new secret**

### Resource Owner Password grant not visible in Okta UI
Okta Identity Engine (OIE) trial accounts don't show ROPC in the UI. Use the API approach in [Step 7](#step-7-enable-resource-owner-password-grant).

### `The authorization server resource does not have any configured default scopes, 'scope' must be provided`
Claude Code's MCP OAuth flow sends a `resource` parameter (RFC 9728) in the authorization request. Okta requires either an explicit `scope` parameter or default scopes configured on the authorization server. See [Appendix A](#appendix-a-claude-code-spa-app-setup) for the fix.

### Trial expiration
The Okta trial lasts 30 days. To continue using it, either:
- Convert to a paid plan
- Sign up for the free [Okta Developer Edition](https://developer.okta.com/signup/)

---

## Appendix A: Claude Code SPA App Setup

Claude Code has native MCP OAuth support — it opens a browser tab for Okta login and manages the JWT lifecycle automatically. This requires a separate **SPA (browser)** app type because Claude Code uses **Authorization Code + PKCE** (a public client flow with no client secret).

> **Note:** The Web app from Steps 2-4 uses ROPC with a client secret (for the Strands agent in `02_demo.ipynb`). Claude Code needs a public client that doesn't require a secret. `03_claude_code_oauth_demo.ipynb` automates all the steps below.

### A1. Create a SPA Application

```bash
curl -X POST -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  https://${OKTA_DOMAIN}/api/v1/apps \
  -d '{
    "name": "oidc_client",
    "label": "AgentCore Gateway - Claude Code (SPA)",
    "signOnMode": "OPENID_CONNECT",
    "settings": {
      "oauthClient": {
        "application_type": "browser",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "redirect_uris": ["http://localhost:8400/callback"],
        "post_logout_redirect_uris": ["http://localhost:8400"]
      }
    },
    "credentials": {
      "oauthClient": {
        "token_endpoint_auth_method": "none"
      }
    }
  }'
```

Note the `client_id` from the response — this is the **SPA Client ID** (no secret needed).

Key differences from the Web app:

| | Web App (02_demo) | SPA App (Claude Code) |
|--|---|---|
| **`application_type`** | `web` | `browser` |
| **`token_endpoint_auth_method`** | `client_secret_basic` | `none` (PKCE only) |
| **Grant type** | `password` (ROPC) | `authorization_code` |
| **Redirect URI** | `localhost:8080` | `localhost:8400` |

### A2. Assign to Everyone Group

```bash
# Get the Everyone group ID
EVERYONE_ID=$(curl -s -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  "https://${OKTA_DOMAIN}/api/v1/groups?q=Everyone&limit=1" | jq -r '.[0].id')

# Assign app to group
curl -X PUT -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  https://${OKTA_DOMAIN}/api/v1/apps/${SPA_CLIENT_ID}/groups/${EVERYONE_ID}
```

### A3. Set Default Scopes

Claude Code follows the MCP OAuth spec (RFC 9728) and sends a `resource` parameter in the authorization request. Okta requires either a `scope` parameter or default scopes. Since Claude Code doesn't send `scope` by default, set the `groups` custom scope as a default:

```bash
# Get the groups scope ID
SCOPE_ID=$(curl -s -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  "https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/scopes" \
  | jq -r '.[] | select(.name == "groups") | .id')

# Get full scope object, set default=true, PUT it back
SCOPE=$(curl -s -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  "https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/scopes/${SCOPE_ID}")

echo "$SCOPE" | jq 'del(._links) | .default = true | .metadataPublish = "ALL_CLIENTS"' | \
  curl -s -X PUT -H "Authorization: SSWS ${OKTA_API_TOKEN}" \
  -H "Content-Type: application/json" \
  "https://${OKTA_DOMAIN}/api/v1/authorizationServers/default/scopes/${SCOPE_ID}" \
  -d @-
```

> **Note:** System scopes (`openid`, `profile`, etc.) cannot be set as default via the API. Only custom scopes support the `default` property.

### A4. Update Gateway `allowedClients`

Add the SPA Client ID to the Gateway's `allowedClients` list (alongside the existing Web app client ID). This is done in `03_claude_code_oauth_demo.ipynb` Cell 4.

### A5. Configure Claude Code

The MCP server config requires explicit `authorizationUrl` and `tokenUrl` because Claude Code's MCP OAuth discovery sends a `resource` parameter that Okta doesn't handle without explicit scopes:

```json
{
  "type": "http",
  "url": "https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp",
  "oauth": {
    "clientId": "<SPA_CLIENT_ID>",
    "callbackPort": 8400,
    "scope": "openid groups",
    "authorizationUrl": "https://<okta-domain>/oauth2/default/v1/authorize",
    "tokenUrl": "https://<okta-domain>/oauth2/default/v1/token"
  }
}
```

> **Workaround:** `claude mcp add-json` may not persist the `scope`, `authorizationUrl`, and `tokenUrl` fields. `03_claude_code_oauth_demo.ipynb` patches `.claude.json` directly to ensure these fields are present.
