# OAuth 2.0 Setup Guide

This guide explains how to configure OAuth 2.0 on the deploy-orchestrator-mcp server and connect it to a ChatGPT custom connector.

---

## Architecture

```
ChatGPT
  └─ OAuth 2.0 Authorization Code (+ PKCE)
       └─ deploy-orchestrator-mcp  (/oauth/authorize → /oauth/token)
            └─ _BearerAuthMiddleware  (validates OAuth tokens and Bearer API key)
                 └─ Credential Store
                      └─ Render / Railway / Supabase / ...
```

OAuth controls **who can call the MCP server from ChatGPT**.  
The Credential Store controls **which provider APIs the MCP server can use**.  
They are independent — both must be configured for a fully operational setup.

---

## Environment Variables

Add these to your Render (or other host) environment configuration:

| Variable | Required | Description |
|---|---|---|
| `OAUTH_CLIENT_ID` | Yes | Client ID you assign to the ChatGPT app (any non-empty string) |
| `OAUTH_CLIENT_SECRET` | Yes | Client secret (generate with `openssl rand -hex 32`) |
| `OAUTH_REDIRECT_URIS` | Yes | Comma-separated allowed redirect URIs (ChatGPT's callback URL) |
| `OAUTH_SCOPES` | No | Space-separated scopes (default: `mcp`) |
| `OAUTH_TOKEN_TTL_SECONDS` | No | Access token lifetime in seconds (default: `3600`) |

**Keeping Bearer API key alongside OAuth** is supported — both can be active simultaneously.  
`MCP_SERVER_API_KEY` continues to work for local / stdio / dev usage.

---

## Step-by-Step: ChatGPT Connector Configuration

### 1. Generate credentials

```bash
# Generate a client secret
openssl rand -hex 32
```

Keep the output as your `OAUTH_CLIENT_SECRET`.

Choose any `OAUTH_CLIENT_ID`, for example: `chatgpt-deploy-orchestrator`.

### 2. Set environment variables on Render

In your Render service → **Environment**, add:

```
OAUTH_CLIENT_ID=chatgpt-deploy-orchestrator
OAUTH_CLIENT_SECRET=<your-generated-secret>
OAUTH_REDIRECT_URIS=https://chatgpt.com/aip/p/<your-plugin-id>/oauth/callback
OAUTH_SCOPES=mcp
OAUTH_TOKEN_TTL_SECONDS=3600
```

> The exact ChatGPT redirect URI is shown in the ChatGPT connector configuration screen after you create the app. Use a placeholder first, then update this variable once you have the real URI.

### 3. Redeploy the service

Trigger a manual deploy on Render to pick up the new environment variables.

### 4. Verify the discovery endpoint

```bash
curl https://deploy-orchestrator-mcp.onrender.com/.well-known/oauth-authorization-server
```

Expected response:

```json
{
  "issuer": "https://deploy-orchestrator-mcp.onrender.com",
  "authorization_endpoint": "https://deploy-orchestrator-mcp.onrender.com/oauth/authorize",
  "token_endpoint": "https://deploy-orchestrator-mcp.onrender.com/oauth/token",
  "response_types_supported": ["code"],
  "grant_types_supported": ["authorization_code"],
  "code_challenge_methods_supported": ["S256", "plain"],
  "token_endpoint_auth_methods_supported": ["client_secret_post"]
}
```

### 5. Configure the ChatGPT custom connector

In ChatGPT → **Explore GPTs** → **Create** → **Configure** → **Actions** → **New action**:

| Field | Value |
|---|---|
| **MCP Server URL** | `https://deploy-orchestrator-mcp.onrender.com/mcp` |
| **Authentication** | OAuth |
| **Client ID** | Value of `OAUTH_CLIENT_ID` |
| **Client Secret** | Value of `OAUTH_CLIENT_SECRET` |
| **Authorization URL** | `https://deploy-orchestrator-mcp.onrender.com/oauth/authorize` |
| **Token URL** | `https://deploy-orchestrator-mcp.onrender.com/oauth/token` |
| **Scope** | `mcp` |

### 6. Update OAUTH_REDIRECT_URIS

After saving the connector, ChatGPT will show you the actual callback URL (something like `https://chatgpt.com/aip/p/<id>/oauth/callback`).  
Update `OAUTH_REDIRECT_URIS` on Render with that exact URL and redeploy.

### 7. Test the connection

Use ChatGPT to call `server_auth_status` — it should return:

```json
{
  "auth_enabled": true,
  "method": "oauth",
  "bearer_api_key_enabled": false,
  "oauth_enabled": true
}
```

---

## PKCE Support

The server supports PKCE (`S256`) for clients that send a `code_challenge`.  
ChatGPT's connector does not currently require PKCE, but it is supported for future compatibility and for other OAuth clients (e.g. browser-based tools).

---

## Token Lifetime and Re-authentication

Access tokens expire after `OAUTH_TOKEN_TTL_SECONDS` (default 1 hour).  
When the token expires, ChatGPT will automatically re-run the OAuth flow.  
Refresh tokens are not implemented — re-auth is the intended mechanism.

---

## Security Notes

- Auth codes are **single-use** and expire after 10 minutes.
- Access tokens are stored in-memory — they are lost on server restart (users will need to re-authenticate).
- The `client_secret` is validated using constant-time comparison to prevent timing attacks.
- No secrets are logged or returned in any server response.
- For multi-instance deployments, consider a shared token store (Redis) — out of scope for the current implementation.
