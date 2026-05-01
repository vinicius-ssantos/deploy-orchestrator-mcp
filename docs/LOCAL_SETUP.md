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

The initial server runs with stdio transport and dry-run tools only.
