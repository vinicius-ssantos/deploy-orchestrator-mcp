# Local setup

## Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . pytest
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e . pytest
```

## Run tests

```bash
pytest -q
```

## Run MCP server locally

```bash
python -m deploy_orchestrator_mcp.server
```

The server runs with stdio transport. Dry-run planning tools are available for all providers, and Render real API tools are available when credentials are configured.

## Configure credentials with .env (Windows PowerShell)

Create `.env` based on `.env.example` and fill at least:

```env
RENDER_API_KEY=your_render_api_key
MCP_REQUIRE_CONFIRMATION=true
MCP_ALLOWED_PROVIDERS=render,railway,supabase
MCP_ALLOWED_ENVIRONMENTS=preview,staging
```

Load `.env` into the current shell session:

```powershell
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $name, $value = $_ -split '=', 2
  [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
}
```

## Render real API smoke checks

After starting the MCP server, run this sequence from your MCP client:

1. `render_validate_credentials`
2. `render_list_services`
3. `render_deploy_staging(service_id="srv_xxx", approval="APPROVED", ci_gate={"allowed": true, "head_sha": "abc123"})`
4. `render_get_deploy_status(service_id="srv_xxx", deploy_id="dep_xxx")`
5. `render_healthcheck(url="https://your-service.onrender.com/healthz")`
