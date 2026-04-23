# Comprehensive Threat Model Report

**Generated**: 2026-04-22 17:29:21
**Current Phase**: 1 - Business Context Analysis
**Overall Completion**: 80.0%

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Business Context](#business-context)
3. [System Architecture](#system-architecture)
4. [Threat Actors](#threat-actors)
5. [Trust Boundaries](#trust-boundaries)
6. [Assets and Flows](#assets-and-flows)
7. [Threats](#threats)
8. [Mitigations](#mitigations)
9. [Assumptions](#assumptions)
10. [Phase Progress](#phase-progress)

## Executive Summary

Centralized MCP (Model Context Protocol) Server Management Platform using AWS Bedrock AgentCore Gateway. The system provides a single security gateway that manages authentication, authorization, and tool routing for multiple AI agent backends. It enables AI agents (Strands SDK and Claude Code) to access insurance domain tools (policy lookups, claims data, CRM contacts) through a centralized gateway that enforces OAuth 2.0 JWT validation via Okta OIDC and fine-grained access control using Cedar policy engine. The architecture includes: (1) AgentCore Gateway as the central proxy with JWT validation and Cedar policy enforcement in ENFORCE mode, (2) Two AWS Lambda backends - PolicyLookup (unrestricted) and ClaimsData (role-based + contextual amount filtering), (3) An ECS/Fargate-hosted CRM MCP server via FastAPI, (4) Okta as external OIDC provider supporting both ROPC grant (for programmatic agents) and Authorization Code + PKCE (for Claude Code browser-based auth). The system handles CONFIDENTIAL insurance claims data with classifications including UNDER INVESTIGATION, HIGH VALUE, and LEGAL HOLD categories. Cedar policies enforce per-user access: open access to policy lookups, restricted claims access for specific users, and contextual constraints limiting query amounts per user identity.

### Key Statistics

- **Total Threats**: 22
- **Total Mitigations**: 20
- **Total Assumptions**: 0
- **System Components**: 11
- **Assets**: 8
- **Threat Actors**: 16

## Business Context

**Description**: Centralized MCP (Model Context Protocol) Server Management Platform using AWS Bedrock AgentCore Gateway. The system provides a single security gateway that manages authentication, authorization, and tool routing for multiple AI agent backends. It enables AI agents (Strands SDK and Claude Code) to access insurance domain tools (policy lookups, claims data, CRM contacts) through a centralized gateway that enforces OAuth 2.0 JWT validation via Okta OIDC and fine-grained access control using Cedar policy engine. The architecture includes: (1) AgentCore Gateway as the central proxy with JWT validation and Cedar policy enforcement in ENFORCE mode, (2) Two AWS Lambda backends - PolicyLookup (unrestricted) and ClaimsData (role-based + contextual amount filtering), (3) An ECS/Fargate-hosted CRM MCP server via FastAPI, (4) Okta as external OIDC provider supporting both ROPC grant (for programmatic agents) and Authorization Code + PKCE (for Claude Code browser-based auth). The system handles CONFIDENTIAL insurance claims data with classifications including UNDER INVESTIGATION, HIGH VALUE, and LEGAL HOLD categories. Cedar policies enforce per-user access: open access to policy lookups, restricted claims access for specific users, and contextual constraints limiting query amounts per user identity.

### Business Features

- **Industry Sector**: Finance
- **Data Sensitivity**: Confidential
- **User Base Size**: Small
- **Geographic Scope**: Regional
- **Regulatory Requirements**: Multiple
- **System Criticality**: High
- **Financial Impact**: High
- **Authentication Requirement**: Federated
- **Deployment Environment**: Cloud-Public
- **Integration Complexity**: Complex

## System Architecture

### Components

| ID | Name | Type | Service Provider | Description |
|---|---|---|---|---|
| C001 | PolicyLookup Lambda | Compute | AWS | Serverless function providing insurance policy lookup tool. Contains hardcoded demo policy data. Accessible to all authenticated users (open Cedar policy). 128MB memory, 30s timeout. |
| C002 | ClaimsData Lambda | Compute | AWS | Serverless function providing insurance claims query tool. Contains hardcoded CONFIDENTIAL claims data with classifications (UNDER INVESTIGATION, HIGH VALUE, LEGAL HOLD). Restricted via Cedar policies: Bob has full access, Alice limited to claims under $100K. Implements Lambda-side fallback filtering based on caller identity. |
| C003 | CRM MCP Server (ECS) | Compute | AWS | Containerized FastAPI MCP server running on ECS/Fargate. Provides CRM contact and account lookup tools via StreamableHTTP MCP protocol on port 8080 (plain HTTP). Serves /mcp and /health endpoints. Public IP assigned, security group allows inbound TCP 8080 from 0.0.0.0/0. No TLS termination. |
| C004 | Strands AI Agent | Other | N/A | Programmatic AI agent using Strands SDK that authenticates via Okta ROPC grant and communicates with the AgentCore Gateway over MCP protocol. Runs locally or on developer machines. |
| C005 | Claude Code Agent | Other | N/A | Claude Code CLI/IDE agent that authenticates via Okta Authorization Code + PKCE flow (browser-based). Communicates with AgentCore Gateway using native MCP OAuth. Caches tokens locally at ~/.claude/oauth-tokens/. |
| C006 | Okta OIDC Provider | Security | Other | External OIDC/OAuth2 identity provider. Issues JWTs with custom claims (groups, client_id). Supports ROPC grant for programmatic agents and Authorization Code + PKCE for browser-based clients. Manages user accounts, groups (analysts, finance-admins), and authentication policies (1FA password-only). |
| C007 | AgentCore Gateway | Network | AWS | Central MCP proxy managed by AWS Bedrock. Validates JWT signatures against Okta JWKS, enforces Cedar policies in ENFORCE mode, routes MCP tool requests to Lambda and ECS backends. Maps JWT sub claim to Cedar principal. Filters unauthorized tools from discovery responses. |
| C008 | Cedar Policy Engine | Security | AWS | Fine-grained authorization engine using Cedar policy language in ENFORCE mode. Evaluates policies based on principal (OAuthUser from JWT sub), action (target/tool name), resource (gateway ARN), and context (tool input parameters). Implements open access, role-based, and contextual constraint patterns. |
| C009 | ECR Repository | Container | AWS | AWS Elastic Container Registry storing the CRM MCP server Docker image. ECS tasks pull images from this registry. |
| C010 | CloudWatch Logs | Analytics | AWS | AWS CloudWatch log group for ECS task logs. 7-day retention. No encryption at rest. No audit logging for Gateway policy decisions. |
| C011 | IAM Roles | Security | AWS | Three IAM roles: (1) Lambda execution role with basic CloudWatch logging, (2) ECS task execution role with ECR pull and CloudWatch push, (3) Gateway role assumed by Bedrock services with lambda:InvokeFunction restricted to PolicyLookup and ClaimsData ARNs only. |

### Connections

| ID | Source | Destination | Protocol | Port | Encrypted | Description |
|---|---|---|---|---|---|---|
| CN001 | C004 | C006 | HTTPS | 443 | Yes | Strands agent authenticates via ROPC grant to obtain JWT access token from Okta |
| CN002 | C005 | C006 | HTTPS | 443 | Yes | Claude Code authenticates via Authorization Code + PKCE flow through browser redirect to Okta |
| CN003 | C004 | C007 | HTTPS | 443 | Yes | Strands agent sends MCP requests with JWT Bearer token to AgentCore Gateway |
| CN004 | C005 | C007 | HTTPS | 443 | Yes | Claude Code sends MCP requests with JWT Bearer token to AgentCore Gateway |
| CN005 | C007 | C006 | HTTPS | 443 | Yes | Gateway fetches Okta JWKS keys to validate JWT signatures |
| CN006 | C007 | C008 | HTTPS | N/A | Yes | Gateway evaluates Cedar policies for each MCP request before routing to backends |
| CN007 | C007 | C001 | HTTPS | N/A | Yes | Gateway invokes PolicyLookup Lambda via AWS internal service invocation (lambda:InvokeFunction) |
| CN008 | C007 | C002 | HTTPS | N/A | Yes | Gateway invokes ClaimsData Lambda via AWS internal service invocation (lambda:InvokeFunction) |
| CN009 | C007 | C003 | HTTP | 8080 | No | Gateway routes MCP requests to CRM ECS server via StreamableHTTP on port 8080. NO TLS - plain HTTP exposed to internet via public IP and open security group. |
| CN010 | C003 | C009 | HTTPS | 443 | Yes | ECS task pulls CRM MCP server Docker image from ECR repository |
| CN011 | C003 | C010 | HTTPS | 443 | Yes | ECS task sends container logs to CloudWatch Logs |

### Data Stores

| ID | Name | Type | Classification | Encrypted at Rest | Description |
|---|---|---|---|---|---|
| D001 | Insurance Policy Data (Lambda Hardcoded) | Other | Internal | No | Hardcoded insurance policy data within PolicyLookup Lambda source code. Contains policy numbers, coverage details, and customer information. No external database - data embedded in deployment package. |
| D002 | Insurance Claims Data (Lambda Hardcoded) | Other | Confidential | No | Hardcoded CONFIDENTIAL insurance claims data within ClaimsData Lambda. Contains claim IDs, amounts ($12K-$250K), statuses, and classifications including UNDER INVESTIGATION, HIGH VALUE, and LEGAL HOLD. No external database. |
| D003 | CRM Contact/Account Data (Hardcoded) | Other | Internal | No | Hardcoded CRM contact and account data within the ECS-hosted FastAPI MCP server. Contains customer names, contact details, and account information. |
| D004 | Okta User Directory | Other | Confidential | Yes | External Okta-managed user directory containing user credentials (passwords), group memberships (analysts, finance-admins), OAuth client configurations, and authentication policies. |
| D005 | Local .env File | Other | Confidential | No | Local plaintext file containing OKTA_CLIENT_SECRET and OKTA_API_TOKEN. Used by setup notebooks and Strands agent scripts. Risk of accidental git commit. |
| D006 | Claude Code OAuth Token Cache | Other | Confidential | No | JWT tokens cached on local filesystem at ~/.claude/oauth-tokens/. Contains access tokens with user identity and group claims. Not encrypted at rest. |
| D007 | Cedar Policy Store | Other | Internal | Yes | Cedar policies stored within AgentCore Gateway. Defines per-user and per-tool authorization rules. Managed via AWS Bedrock APIs. Changes affect all authorization decisions. |

## Threat Actors

### Insider

- **Type**: ThreatActorType.INSIDER
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Revenge
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 5/10
- **Description**: An employee or contractor with legitimate access to the system

### External Attacker

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 3/10
- **Description**: An external individual or group attempting to gain unauthorized access

### Nation-state Actor

- **Type**: ThreatActorType.NATION_STATE
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Espionage, Political
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 1/10
- **Description**: A government-sponsored group with advanced capabilities

### Hacktivist

- **Type**: ThreatActorType.HACKTIVIST
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Ideology, Political
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 6/10
- **Description**: An individual or group motivated by ideological or political beliefs

### Organized Crime

- **Type**: ThreatActorType.ORGANIZED_CRIME
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 2/10
- **Description**: A criminal organization with significant resources

### Competitor

- **Type**: ThreatActorType.COMPETITOR
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Espionage
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 7/10
- **Description**: A business competitor seeking competitive advantage

### Script Kiddie

- **Type**: ThreatActorType.SCRIPT_KIDDIE
- **Capability Level**: CapabilityLevel.LOW
- **Motivations**: Curiosity, Reputation
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 9/10
- **Description**: An inexperienced attacker using pre-made tools

### Disgruntled Employee

- **Type**: ThreatActorType.DISGRUNTLED_EMPLOYEE
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Revenge
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 4/10
- **Description**: A current or former employee with a grievance

### Privileged User

- **Type**: ThreatActorType.PRIVILEGED_USER
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial, Accidental
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 8/10
- **Description**: A user with elevated privileges who may abuse them or make mistakes

### Third Party

- **Type**: ThreatActorType.THIRD_PARTY
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Accidental
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 10/10
- **Description**: A vendor, partner, or service provider with access to the system

### Malicious Insider (Authorized User)

- **Type**: ThreatActorType.INSIDER
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Financial, Espionage
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 9/10
- **Description**: An authorized user (e.g., Alice or Bob) who abuses their legitimate access to exfiltrate confidential claims data, escalate privileges beyond Cedar policy constraints, or manipulate tool inputs to bypass contextual filters (e.g., max_amount). Has valid Okta credentials and JWT tokens.

### External Attacker (Network)

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial, Espionage
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 10/10
- **Description**: External attacker targeting the publicly exposed ECS CRM server (0.0.0.0/0 on port 8080, no TLS, no auth). Can directly access CRM data bypassing the Gateway entirely. Can also attempt credential theft, JWT token theft from cached files, or man-in-the-middle attacks on unencrypted HTTP connections.

### Compromised AI Agent

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.MEDIUM
- **Motivations**: Espionage, Disruption
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 8/10
- **Description**: An AI agent (Strands or Claude Code) that has been compromised via prompt injection, supply chain attack on dependencies, or malicious MCP tool responses. Could exfiltrate data through tool calls, manipulate inputs to bypass Cedar constraints, or use cached tokens for unauthorized access.

### Credential Thief (Local Access)

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.LOW
- **Motivations**: Financial
- **Resources**: ResourceLevel.LIMITED
- **Relevant**: Yes
- **Priority**: 7/10
- **Description**: Attacker who gains access to developer workstation or CI/CD environment and steals plaintext secrets from .env file (Okta client secret, API token) or cached JWT tokens from ~/.claude/oauth-tokens/. Could also obtain credentials from git history if .env was committed.

### Okta Account Compromise

- **Type**: ThreatActorType.EXTERNAL
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial, Espionage
- **Resources**: ResourceLevel.EXTENSIVE
- **Relevant**: Yes
- **Priority**: 8/10
- **Description**: Attacker who compromises Okta admin account or API token to modify authentication policies, create rogue users, alter group memberships, or issue tokens with elevated claims. Especially dangerous given 1FA-only policy (no MFA). Could undermine all downstream authorization.

### Cedar Policy Manipulator

- **Type**: ThreatActorType.INSIDER
- **Capability Level**: CapabilityLevel.HIGH
- **Motivations**: Financial, Espionage
- **Resources**: ResourceLevel.MODERATE
- **Relevant**: Yes
- **Priority**: 7/10
- **Description**: Insider with AWS console/API access who modifies Cedar policies to grant unauthorized access, weaken contextual constraints, or change ENFORCE mode. Could also modify Gateway configuration to add unauthorized targets or disable JWT validation. No audit trail for policy changes.

## Trust Boundaries

### Trust Zones

#### Internet

- **Trust Level**: TrustLevel.UNTRUSTED
- **Description**: The public internet, considered untrusted

#### DMZ

- **Trust Level**: TrustLevel.LOW
- **Description**: Demilitarized zone for public-facing services

#### Application

- **Trust Level**: TrustLevel.MEDIUM
- **Description**: Zone containing application servers and services

#### Data

- **Trust Level**: TrustLevel.HIGH
- **Description**: Zone containing databases and data storage

#### Admin

- **Trust Level**: TrustLevel.FULL
- **Description**: Administrative zone with highest privileges

#### Client Zone (Untrusted)

- **Trust Level**: TrustLevel.UNTRUSTED
- **Description**: Local developer/user machines running AI agents (Strands SDK, Claude Code). Untrusted environment - tokens cached on filesystem, .env files with secrets, no centralized control.

#### External Identity Zone (Okta)

- **Trust Level**: TrustLevel.HIGH
- **Description**: Okta SaaS identity platform managing authentication, user directory, OAuth clients, and token issuance. High trust but externally managed - dependent on Okta's security posture.

#### AWS Gateway Zone

- **Trust Level**: TrustLevel.HIGH
- **Description**: AWS Bedrock AgentCore Gateway with Cedar Policy Engine. Handles JWT validation, policy enforcement, and request routing. Managed AWS service with high trust level.

#### AWS Backend Zone (Lambda)

- **Trust Level**: TrustLevel.FULL
- **Description**: Serverless Lambda backends (PolicyLookup, ClaimsData) running in isolated AWS execution environments. Fully trusted - only reachable via Gateway IAM role invocation. Contains confidential insurance data.

#### AWS Backend Zone (ECS)

- **Trust Level**: TrustLevel.MEDIUM
- **Description**: ECS/Fargate container running CRM MCP server. Medium trust - public IP assigned, security group allows 0.0.0.0/0 on port 8080, plain HTTP (no TLS). Directly accessible from internet bypassing Gateway.

### Trust Boundaries

#### Internet Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Web Application Firewall, DDoS Protection, TLS Encryption
- **Description**: Boundary between the internet and internal systems

#### DMZ Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Network Firewall, Intrusion Detection System, API Gateway
- **Description**: Boundary between public-facing services and internal applications

#### Data Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Database Firewall, Encryption, Access Control Lists
- **Description**: Boundary protecting data storage systems

#### Admin Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: Privileged Access Management, Multi-Factor Authentication, Audit Logging
- **Description**: Boundary for administrative access

#### Internet / Public Network Boundary

- **Type**: BoundaryType.NETWORK
- **Controls**: TLS/HTTPS encryption, JWT Bearer token validation, Okta JWKS signature verification, Client ID allowlist
- **Description**: Boundary between untrusted client zone and cloud services. All traffic crosses the public internet. Protected by HTTPS and OAuth token-based authentication.

#### Gateway Authorization Boundary

- **Type**: BoundaryType.PROCESS
- **Controls**: Cedar policy engine (ENFORCE mode), Per-user principal mapping, Contextual input constraints (max_amount), Tool-level action authorization, Tool discovery filtering
- **Description**: Primary authorization boundary within AWS. Cedar policies evaluated before any request reaches backend services. Enforces per-user, per-tool, and per-input authorization.

#### AWS Account Boundary

- **Type**: BoundaryType.ACCOUNT
- **Controls**: IAM role-based access, Lambda function ARN restriction, AWS service-level isolation
- **Description**: AWS account-level boundary protecting Lambda backends. Only accessible via Gateway IAM role with scoped lambda:InvokeFunction permissions.

#### ECS Public Network Boundary (WEAK)

- **Type**: BoundaryType.NETWORK
- **Controls**: Security group (port 8080 open to 0.0.0.0/0), No TLS, No authentication on ECS endpoint
- **Description**: WEAK boundary around ECS CRM server. Public IP with security group allowing all inbound on port 8080. No TLS termination, no authentication. CRM data accessible by anyone who discovers the IP. CRITICAL VULNERABILITY.

## Assets and Flows

### Assets

| ID | Name | Type | Classification | Sensitivity | Criticality | Owner |
|---|---|---|---|---|---|---|
| A001 | JWT Access Tokens | AssetType.CREDENTIAL | AssetClassification.CONFIDENTIAL | 5 | 5 | N/A |
| A002 | User Credentials (Okta) | AssetType.CREDENTIAL | AssetClassification.RESTRICTED | 5 | 5 | N/A |
| A003 | Okta Client Secret | AssetType.CREDENTIAL | AssetClassification.RESTRICTED | 5 | 5 | N/A |
| A004 | Okta API Token | AssetType.CREDENTIAL | AssetClassification.RESTRICTED | 5 | 5 | N/A |
| A005 | Insurance Claims Data | AssetType.DATA | AssetClassification.CONFIDENTIAL | 4 | 4 | N/A |
| A006 | Insurance Policy Data | AssetType.DATA | AssetClassification.INTERNAL | 3 | 3 | N/A |
| A007 | Cedar Authorization Policies | AssetType.CONFIG | AssetClassification.INTERNAL | 4 | 5 | N/A |
| A008 | MCP Tool Request/Response Payloads | AssetType.DATA | AssetClassification.CONFIDENTIAL | 4 | 3 | N/A |

### Asset Flows

| ID | Asset | Source | Destination | Protocol | Encrypted | Risk Level |
|---|---|---|---|---|---|---|
| F001 | User Credentials (Okta) | C001 | C003 | HTTPS | Yes | 4 |
| F002 | JWT Access Tokens | C003 | C001 | HTTPS | Yes | 3 |
| F003 | JWT Access Tokens | C003 | C002 | HTTPS | Yes | 3 |
| F004 | JWT Access Tokens | C001 | C004 | HTTPS | Yes | 3 |
| F005 | JWT Access Tokens | C002 | C004 | HTTPS | Yes | 3 |
| F006 | MCP Tool Request/Response Payloads | C004 | C006 | HTTPS | Yes | 1 |
| F007 | Insurance Policy Data | C006 | C004 | HTTPS | Yes | 2 |
| F008 | MCP Tool Request/Response Payloads | C004 | C007 | HTTPS | Yes | 2 |
| F009 | Insurance Claims Data | C007 | C004 | HTTPS | Yes | 3 |

## Threats

### Identified Threats

#### T1: External attacker

**Statement**: A External attacker Discovery of ECS public IP and open port 8080 can Directly access CRM MCP server bypassing AgentCore Gateway via public IP on port 8080, which leads to Full unauthorized access to CRM contact/account data without authentication or authorization

- **Prerequisites**: Discovery of ECS public IP and open port 8080
- **Action**: Directly access CRM MCP server bypassing AgentCore Gateway via public IP on port 8080
- **Impact**: Full unauthorized access to CRM contact/account data without authentication or authorization
- **Impacted Assets**: A014
- **Tags**: ECS, bypass, no-auth, CRITICAL

#### T2: Network attacker (MITM)

**Statement**: A Network attacker (MITM) Network position between Gateway and ECS server can Intercept unencrypted HTTP traffic on port 8080 between Gateway and ECS CRM server, which leads to Exposure of CRM data and MCP request/response payloads in transit

- **Prerequisites**: Network position between Gateway and ECS server
- **Action**: Intercept unencrypted HTTP traffic on port 8080 between Gateway and ECS CRM server
- **Impact**: Exposure of CRM data and MCP request/response payloads in transit
- **Impacted Assets**: A014, A016
- **Tags**: MITM, no-TLS, HTTP

#### T3: Credential thief with local workstation access

**Statement**: A Credential thief with local workstation access Access to developer machine filesystem or git repository can Steal Okta client secret and API token from plaintext .env file or git history, which leads to Full Okta admin access; create users, modify groups, issue tokens, bypass all auth

- **Prerequisites**: Access to developer machine filesystem or git repository
- **Action**: Steal Okta client secret and API token from plaintext .env file or git history
- **Impact**: Full Okta admin access; create users, modify groups, issue tokens, bypass all auth
- **Impacted Assets**: A010, A011
- **Tags**: secrets, env-file, credential-theft

#### T4: Attacker with stolen JWT or local file access

**Statement**: A Attacker with stolen JWT or local file access Access to ~/.claude/oauth-tokens/ directory on user machine can Steal cached JWT access tokens from Claude Code local filesystem cache, which leads to Impersonate user for up to 60 minutes; access all their authorized tools

- **Prerequisites**: Access to ~/.claude/oauth-tokens/ directory on user machine
- **Action**: Steal cached JWT access tokens from Claude Code local filesystem cache
- **Impact**: Impersonate user for up to 60 minutes; access all their authorized tools
- **Impacted Assets**: A008
- **Tags**: token-theft, local-cache, impersonation

#### T5: Authorized user (Alice)

**Statement**: A Authorized user (Alice) Valid Okta credentials and Cedar policy with contextual max_amount constraint can Manipulate MCP tool inputs to bypass Cedar contextual constraints on claims queries, which leads to Access to high-value claims data ($100K+) beyond authorized limit

- **Prerequisites**: Valid Okta credentials and Cedar policy with contextual max_amount constraint
- **Action**: Manipulate MCP tool inputs to bypass Cedar contextual constraints on claims queries
- **Impact**: Access to high-value claims data ($100K+) beyond authorized limit
- **Impacted Assets**: A012
- **Tags**: policy-bypass, Cedar, contextual-constraint

#### T6: Attacker who compromises Okta admin account

**Statement**: A Attacker who compromises Okta admin account Compromised Okta admin credentials or stolen API token (1FA only, no MFA) can Modify Okta auth policies, create rogue users, alter group memberships, issue elevated tokens, which leads to Complete auth bypass; tokens accepted by Gateway with arbitrary claims

- **Prerequisites**: Compromised Okta admin credentials or stolen API token (1FA only, no MFA)
- **Action**: Modify Okta auth policies, create rogue users, alter group memberships, issue elevated tokens
- **Impact**: Complete auth bypass; tokens accepted by Gateway with arbitrary claims
- **Impacted Assets**: A008, A012, A013, A014
- **Tags**: Okta-compromise, IdP, 1FA, no-MFA

#### T7: Insider with AWS API/console access

**Statement**: A Insider with AWS API/console access AWS IAM permissions to manage Bedrock AgentCore Gateway and Cedar policies can Modify Cedar policies to weaken authorization or change ENFORCE to MONITOR mode, which leads to All authorization controls bypassed; any authenticated user accesses all tools and data

- **Prerequisites**: AWS IAM permissions to manage Bedrock AgentCore Gateway and Cedar policies
- **Action**: Modify Cedar policies to weaken authorization or change ENFORCE to MONITOR mode
- **Impact**: All authorization controls bypassed; any authenticated user accesses all tools and data
- **Impacted Assets**: A015, A012, A014
- **Tags**: Cedar-tampering, policy-modification, no-audit

#### T8: Compromised AI agent via prompt injection

**Statement**: A Compromised AI agent via prompt injection Malicious content in MCP tool responses or user prompts fed to the AI agent can Exfiltrate sensitive data via side channels or craft malicious tool calls using user's token, which leads to Confidential claims/policy data leaked; unauthorized actions with user's permissions

- **Prerequisites**: Malicious content in MCP tool responses or user prompts fed to the AI agent
- **Action**: Exfiltrate sensitive data via side channels or craft malicious tool calls using user's token
- **Impact**: Confidential claims/policy data leaked; unauthorized actions with user's permissions
- **Impacted Assets**: A012, A013, A016
- **Tags**: prompt-injection, AI-agent, exfiltration

#### T9: External attacker or automated scanner

**Statement**: A External attacker or automated scanner Network access to AgentCore Gateway HTTPS endpoint can Flood Gateway with MCP requests to exhaust Lambda concurrency or ECS resources, which leads to Denial of service; legitimate agents unable to access tools; Lambda cost explosion

- **Prerequisites**: Network access to AgentCore Gateway HTTPS endpoint
- **Action**: Flood Gateway with MCP requests to exhaust Lambda concurrency or ECS resources
- **Impact**: Denial of service; legitimate agents unable to access tools; Lambda cost explosion
- **Impacted Assets**: A016
- **Tags**: DoS, rate-limiting, cost

#### T10: Any party with access to system

**Statement**: A Any party with access to system Absence of audit logging for Gateway policy decisions and Cedar evaluations can Perform unauthorized access without detection due to missing audit trail, which leads to Inability to detect breaches, investigate incidents, or prove compliance

- **Prerequisites**: Absence of audit logging for Gateway policy decisions and Cedar evaluations
- **Action**: Perform unauthorized access without detection due to missing audit trail
- **Impact**: Inability to detect breaches, investigate incidents, or prove compliance
- **Impacted Assets**: A012, A013, A014, A015
- **Tags**: no-audit, logging, compliance, repudiation

#### T11: Attacker exploiting ROPC grant flow

**Statement**: A Attacker exploiting ROPC grant flow Knowledge of Okta token endpoint and valid client_id (discoverable from config) can Brute-force user passwords via ROPC grant endpoint without rate limiting or MFA, which leads to Account takeover; valid JWT obtained for victim with all their permissions

- **Prerequisites**: Knowledge of Okta token endpoint and valid client_id (discoverable from config)
- **Action**: Brute-force user passwords via ROPC grant endpoint without rate limiting or MFA
- **Impact**: Account takeover; valid JWT obtained for victim with all their permissions
- **Impacted Assets**: A009, A008
- **Tags**: ROPC, brute-force, password, 1FA

#### T12: Attacker with Lambda deployment access

**Statement**: A Attacker with Lambda deployment access Read access to Lambda source code or deployment artifacts can Extract hardcoded confidential data from Lambda source code (claims, policies), which leads to Bulk exposure of all insurance claims and policy data bypassing Gateway controls

- **Prerequisites**: Read access to Lambda source code or deployment artifacts
- **Action**: Extract hardcoded confidential data from Lambda source code (claims, policies)
- **Impact**: Bulk exposure of all insurance claims and policy data bypassing Gateway controls
- **Impacted Assets**: A012, A013
- **Tags**: hardcoded-data, Lambda-source, data-exposure

#### T13: Credential thief with local workstation access

**Statement**: A Credential thief with local workstation access Access to developer machine filesystem or git repository can Steal Okta client secret and API token from plaintext .env file or git history, which leads to Full Okta admin access; create users, modify groups, issue tokens, bypass all auth

- **Prerequisites**: Access to developer machine filesystem or git repository
- **Action**: Steal Okta client secret and API token from plaintext .env file or git history
- **Impact**: Full Okta admin access; create users, modify groups, issue tokens, bypass all auth
- **Impacted Assets**: A003, A004
- **Tags**: secrets, env-file, credential-theft

#### T14: Attacker with stolen JWT or local file access

**Statement**: A Attacker with stolen JWT or local file access Access to ~/.claude/oauth-tokens/ on user machine can Steal cached JWT access tokens from Claude Code local filesystem cache, which leads to Impersonate user for up to 60 minutes; access all their authorized tools and data

- **Prerequisites**: Access to ~/.claude/oauth-tokens/ on user machine
- **Action**: Steal cached JWT access tokens from Claude Code local filesystem cache
- **Impact**: Impersonate user for up to 60 minutes; access all their authorized tools and data
- **Impacted Assets**: A001
- **Tags**: token-theft, local-cache, impersonation

#### T15: Attacker exploiting ROPC grant flow

**Statement**: A Attacker exploiting ROPC grant flow Knowledge of Okta token endpoint and valid client_id (discoverable from config) can Brute-force user passwords via ROPC grant endpoint without rate limiting or MFA, which leads to Account takeover; valid JWT obtained for victim with all their permissions

- **Prerequisites**: Knowledge of Okta token endpoint and valid client_id (discoverable from config)
- **Action**: Brute-force user passwords via ROPC grant endpoint without rate limiting or MFA
- **Impact**: Account takeover; valid JWT obtained for victim with all their permissions
- **Impacted Assets**: A002, A001
- **Tags**: ROPC, brute-force, 1FA, no-MFA

#### T16: Attacker who compromises Okta admin account

**Statement**: A Attacker who compromises Okta admin account Compromised Okta admin credentials or stolen API token (1FA only) can Modify Okta auth policies, create rogue users, alter groups, issue elevated tokens, which leads to Complete auth bypass; tokens accepted by Gateway with arbitrary claims

- **Prerequisites**: Compromised Okta admin credentials or stolen API token (1FA only)
- **Action**: Modify Okta auth policies, create rogue users, alter groups, issue elevated tokens
- **Impact**: Complete auth bypass; tokens accepted by Gateway with arbitrary claims
- **Impacted Assets**: A001, A005, A006
- **Tags**: Okta-compromise, IdP, 1FA

#### T17: Authorized user (contextual user)

**Statement**: A Authorized user (contextual user) Valid Okta credentials and Cedar policy with contextual max_amount constraint can Manipulate MCP tool inputs to bypass Cedar contextual constraints on claims queries, which leads to Access to high-value claims data ($100K+) beyond authorized limit

- **Prerequisites**: Valid Okta credentials and Cedar policy with contextual max_amount constraint
- **Action**: Manipulate MCP tool inputs to bypass Cedar contextual constraints on claims queries
- **Impact**: Access to high-value claims data ($100K+) beyond authorized limit
- **Impacted Assets**: A005
- **Tags**: policy-bypass, Cedar, contextual-constraint

#### T18: Insider with AWS API/console access

**Statement**: A Insider with AWS API/console access AWS IAM permissions to manage Bedrock AgentCore and Cedar policies can Modify Cedar policies to weaken authorization or change ENFORCE to MONITOR mode, which leads to All authorization bypassed; any authenticated user accesses all tools and data

- **Prerequisites**: AWS IAM permissions to manage Bedrock AgentCore and Cedar policies
- **Action**: Modify Cedar policies to weaken authorization or change ENFORCE to MONITOR mode
- **Impact**: All authorization bypassed; any authenticated user accesses all tools and data
- **Impacted Assets**: A007, A005
- **Tags**: Cedar-tampering, no-audit

#### T19: Compromised AI agent via prompt injection

**Statement**: A Compromised AI agent via prompt injection Malicious content in MCP tool responses or user prompts can Exfiltrate sensitive data via side channels or craft malicious tool calls using user's token, which leads to Confidential claims/policy data leaked; unauthorized actions with user's permissions

- **Prerequisites**: Malicious content in MCP tool responses or user prompts
- **Action**: Exfiltrate sensitive data via side channels or craft malicious tool calls using user's token
- **Impact**: Confidential claims/policy data leaked; unauthorized actions with user's permissions
- **Impacted Assets**: A005, A006, A008
- **Tags**: prompt-injection, AI-agent, exfiltration

#### T20: Any party with access to system

**Statement**: A Any party with access to system Absence of audit logging for Gateway policy decisions and Cedar evaluations can Perform unauthorized access without detection due to missing audit trail, which leads to Inability to detect breaches, investigate incidents, or prove compliance

- **Prerequisites**: Absence of audit logging for Gateway policy decisions and Cedar evaluations
- **Action**: Perform unauthorized access without detection due to missing audit trail
- **Impact**: Inability to detect breaches, investigate incidents, or prove compliance
- **Impacted Assets**: A005, A006, A007
- **Tags**: no-audit, logging, compliance

#### T21: External attacker or automated scanner

**Statement**: A External attacker or automated scanner Network access to AgentCore Gateway HTTPS endpoint can Flood Gateway with MCP requests to exhaust Lambda concurrency limits, which leads to Denial of service; legitimate agents unable to access tools; Lambda cost explosion

- **Prerequisites**: Network access to AgentCore Gateway HTTPS endpoint
- **Action**: Flood Gateway with MCP requests to exhaust Lambda concurrency limits
- **Impact**: Denial of service; legitimate agents unable to access tools; Lambda cost explosion
- **Impacted Assets**: A008
- **Tags**: DoS, rate-limiting, cost

#### T22: Attacker with Lambda deployment access

**Statement**: A Attacker with Lambda deployment access Read access to Lambda source code or deployment artifacts can Extract hardcoded confidential data from Lambda source code, which leads to Bulk exposure of all insurance claims and policy data bypassing Gateway

- **Prerequisites**: Read access to Lambda source code or deployment artifacts
- **Action**: Extract hardcoded confidential data from Lambda source code
- **Impact**: Bulk exposure of all insurance claims and policy data bypassing Gateway
- **Impacted Assets**: A005, A006
- **Tags**: hardcoded-data, Lambda-source

## Mitigations

### Identified Mitigations

#### M1: Restrict ECS security group to Gateway-only traffic. Replace 0.0.0.0/0 ingress with the Gateway's VPC CIDR or specific security group. Place ECS in private subnet with no public IP.

**Addresses Threats**: T1

#### M2: Add TLS termination for ECS CRM server. Deploy an ALB with HTTPS listener and ACM certificate in front of the ECS service, or enable TLS directly in the FastAPI/Uvicorn server.

**Addresses Threats**: T2

#### M3: Move secrets from plaintext .env to AWS Secrets Manager or environment-specific vaults. Add .env to .gitignore. Rotate Okta API token and client secret immediately if ever committed to git.

**Addresses Threats**: T3, T6

#### M4: Enable MFA on Okta for all users. Replace 1FA password-only authentication policy with at least 2FA. This protects against ROPC brute-force and credential stuffing attacks.

**Addresses Threats**: T6, T11

#### M5: Implement comprehensive audit logging for Gateway policy decisions, Cedar evaluations, tool invocations, and access denials. Send logs to CloudWatch with extended retention and alerting.

**Addresses Threats**: T5, T7, T10

#### M6: Implement rate limiting on the AgentCore Gateway and configure Lambda reserved concurrency to prevent DoS and cost explosion from request flooding.

**Addresses Threats**: T9

#### M7: Deprecate ROPC grant flow in favor of client_credentials grant with service accounts, or device authorization flow. ROPC exposes passwords to the client application and is deprecated in OAuth 2.1.

**Addresses Threats**: T11

#### M8: Restrict AWS IAM permissions for Cedar policy management. Require approval workflow for policy changes. Enable CloudTrail logging for all Bedrock AgentCore API calls.

**Addresses Threats**: T5, T7

#### M9: Move sensitive data from hardcoded Lambda source to encrypted data stores (DynamoDB with KMS, or Secrets Manager). Eliminates bulk data exposure from source code access.

**Addresses Threats**: T12

#### M10: Add ECS-level authentication for the CRM MCP server. Require API key, mTLS, or IAM-based auth so only the Gateway can invoke it, even if directly reachable.

**Addresses Threats**: T1

#### M11: Implement prompt injection defenses in AI agents: input/output sanitization, tool call validation, human-in-the-loop for sensitive operations, and sandboxing of agent execution.

**Addresses Threats**: T8

#### M12: Encrypt cached JWT tokens at rest on local filesystem. Use OS-level credential stores (macOS Keychain, Windows Credential Manager) instead of plaintext file storage.

**Addresses Threats**: T4

#### M13: Move secrets from plaintext .env to AWS Secrets Manager. Add .env to .gitignore. Rotate Okta API token and client secret if ever committed to git.

**Addresses Threats**: T13, T16

#### M14: Encrypt cached JWT tokens at rest. Use OS-level credential stores (macOS Keychain) instead of plaintext filesystem. Reduce token TTL.

**Addresses Threats**: T14

#### M15: Enable MFA on Okta for all users. Replace 1FA password-only policy with at least 2FA. Deprecate ROPC grant in favor of client_credentials for programmatic agents.

**Addresses Threats**: T15, T16

#### M16: Implement comprehensive audit logging for Gateway policy decisions, Cedar evaluations, tool invocations, and access denials. Extend CloudWatch retention to 90+ days.

**Addresses Threats**: T17, T18, T20

#### M17: Restrict AWS IAM permissions for Cedar policy management. Require approval workflow for changes. Enable CloudTrail for all Bedrock AgentCore API calls.

**Addresses Threats**: T17, T18

#### M18: Implement rate limiting on AgentCore Gateway. Configure Lambda reserved concurrency and billing alarms to prevent DoS and cost explosion.

**Addresses Threats**: T21

#### M19: Move sensitive data from hardcoded Lambda source to encrypted data stores (DynamoDB with KMS). Eliminates bulk data exposure from source code access.

**Addresses Threats**: T22

#### M20: Implement prompt injection defenses in AI agents: input/output sanitization, tool call validation, human-in-the-loop for sensitive operations, execution sandboxing.

**Addresses Threats**: T19

## Assumptions

*No assumptions defined.*

## Phase Progress

| Phase | Name | Completion |
|---|---|---|
| 1 | Business Context Analysis | 100% ✅ |
| 2 | Architecture Analysis | 100% ✅ |
| 3 | Threat Actor Analysis | 100% ✅ |
| 4 | Trust Boundary Analysis | 100% ✅ |
| 5 | Asset Flow Analysis | 100% ✅ |
| 6 | Threat Identification | 100% ✅ |
| 7 | Mitigation Planning | 100% ✅ |
| 7.5 | Code Validation Analysis | 0% ⏳ |
| 8 | Residual Risk Analysis | 0% ⏳ |
| 9 | Output Generation and Documentation | 100% ✅ |

---

*This threat model report was generated automatically by the Threat Modeling MCP Server.*
