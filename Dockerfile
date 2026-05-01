FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip && python -m pip install -e .

CMD ["python", "-m", "deploy_orchestrator_mcp.server"]
