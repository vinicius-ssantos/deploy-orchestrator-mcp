# Orchestrator Refactor MVP — Plano de Slices

## Visão Geral

Este documento descreve o plano de refatoração do `deploy-orchestrator-mcp` em cinco slices independentes e sequenciais. O objetivo é tornar cada responsabilidade do orquestrador isolada, testável e consumidora explícita dos contratos do `github-unified-mcp`.

Nenhum código de produção é alterado neste documento — ele serve apenas como guia de planejamento e rastreamento.

---

## Contrato com `github-unified-mcp` — `ci_gate_check`

O orquestrador deve consumir obrigatoriamente os seguintes campos da resposta de `ci_gate_check`:

| Campo | Tipo | Descrição | Obrigatoriedade |
|---|---|---|---|
| `allowed` | `bool` | `true` se todos os checks passaram e o deploy pode prosseguir | **Obrigatório** — bloqueia execução se `false` ou ausente |
| `blocking_checks` | `list[str]` | Nomes dos checks que estão impedindo o gate | **Obrigatório** — deve ser registrado no audit event e exposto ao chamador |
| `summary` | `str` | Texto legível descrevendo o estado geral do CI | **Obrigatório** — deve ser retornado no campo `ci_summary` da resposta do orquestrador |

**Regra invariante:** `allowed=false` ou ausência de `allowed` bloqueia toda execução fora de `dry-run`, independentemente de qualquer outra configuração.

---

## Mapa dos Slices

### S1 — Stack Detection Isolado e Testável

**Descrição:** Extrair e consolidar a lógica de detecção de stack (runtime, framework, presença de Dockerfile, necessidade de banco de dados) em um módulo puro, sem efeitos colaterais e sem dependências de execução. O módulo deve ser chamável com apenas uma lista de arquivos e retornar um `StackProfile` tipado.

**Entradas:**
- Lista de nomes de arquivos do repositório (`list[str]`)

**Saídas:**
- `StackProfile`: dicionário tipado com campos `runtime`, `framework`, `has_dockerfile`, `needs_database`, `needs_supabase`, `is_frontend`, `frontend_framework`, `repo_full_name`

**Critério de Done:**
- Módulo `stack_detector.py` existe e exporta função `detect_stack(files: list[str]) -> StackProfile`
- `analyzer.py` e `recommender.py` delegam para `detect_stack` (sem duplicação de lógica)
- Testes unitários cobrem os runtimes Python, Node, Java, Go e os frameworks Vite, Next.js
- Nenhuma importação de `planner`, `execution` ou providers dentro do módulo

**Depende de:** —

---

### S2 — Plan Generation Desacoplado de Execução

**Descrição:** Garantir que `generate_deployment_plan` em `planner.py` não contenha lógica de execução, aprovação ou CI gate. O planner deve apenas receber um `StackProfile` e um `environment`, e retornar um `DeploymentPlan` serializado — sem decidir se o deploy pode ou não ocorrer.

**Entradas:**
- `StackProfile` (saída de S1)
- `environment: str` (`"staging"` | `"production"`)
- `policy: dict | None`

**Saídas:**
- `DeploymentPlan`: dicionário com campos `provider`, `service_name`, `environment`, `steps`, `database_plan`, `policy_result`, `approval_required`, `mode`

**Critério de Done:**
- `generate_deployment_plan` não importa nem chama nada de `execution.py`
- Testes cobrem os provedores Render, Railway, Fly e o caso sem banco de dados
- O campo `mode` do plano reflete apenas a intenção informada (`"dry-run"` | `"execute"`), nunca uma decisão de gate

**Depende de:** S1

---

### S3 — Execution Gate com `ci_gate.allowed` Obrigatório

**Descrição:** Refatorar `evaluate_execution_gate` em `execution.py` para consumir explicitamente os três campos do contrato `ci_gate_check` (`allowed`, `blocking_checks`, `summary`). A ausência de qualquer um desses campos deve gerar erro estruturado — não silencioso. O gate deve retornar `allowed=false` com `blocking_checks` populado sempre que o CI não estiver verde.

**Entradas:**
- `plan: DeploymentPlan` (saída de S2)
- `ci_gate: dict` com campos `allowed: bool`, `blocking_checks: list[str]`, `summary: str`
- `approval: bool | str | None`
- `mode: str`

**Saídas:**
- `GateResult`: dicionário com campos `ok`, `allowed`, `mode`, `blocking_checks`, `ci_summary`, `reasons`, `missing_fields`, `audit_event`

**Critério de Done:**
- `_validate_ci_gate` valida `allowed`, `blocking_checks` e `summary` — retorna erros estruturados se ausentes
- Resposta do gate sempre inclui `blocking_checks` e `ci_summary`
- Testes cobrem: gate bloqueado por CI, gate bloqueado por policy, gate bloqueado por falta de aprovação, gate liberado
- `missing_fields` lista exatamente os campos ausentes do payload `ci_gate`

**Depende de:** S2

---

### S4 — Render Deploy + Logs + Healthcheck

**Descrição:** Implementar (ou consolidar em) um módulo `render_deploy.py` que encapsule o fluxo completo de deploy no Render: triggerar o deploy, aguardar conclusão com polling, coletar logs e executar healthcheck final. Cada etapa deve ser uma função pura e testável separadamente.

**Entradas:**
- `DeploymentPlan` com `provider="render"` (saída de S2)
- `GateResult` com `allowed=true` (saída de S3)
- Credenciais Render (`api_key`, `service_id`)

**Saídas:**
- `DeployResult`: dicionário com campos `deploy_id`, `status`, `logs_url`, `healthcheck_status`, `healthcheck_url`, `duration_seconds`

**Critério de Done:**
- Funções `trigger_deploy`, `poll_deploy_status`, `fetch_logs`, `run_healthcheck` existem e são testáveis com mocks da API Render
- O módulo não chama `evaluate_execution_gate` — recebe `GateResult` já avaliado
- Testes cobrem: deploy bem-sucedido, deploy com falha, healthcheck timeout
- `render_workflows.py` e `render_api.py` delegam para o novo módulo sem duplicação

**Depende de:** S3

---

### S5 — Rollback Staging

**Descrição:** Implementar suporte a rollback em ambiente de staging para o provedor Render. O rollback deve ser acionado explicitamente (nunca automático), registrado em audit trail, e verificar que o ambiente alvo é `staging` antes de prosseguir.

**Entradas:**
- `service_id: str` — identificador do serviço Render
- `deploy_id: str` — ID do deploy anterior para o qual reverter
- `environment: str` — deve ser `"staging"` (rollback em `production` é bloqueado neste slice)
- Credenciais Render

**Saídas:**
- `RollbackResult`: dicionário com campos `rolled_back_to`, `status`, `audit_event`, `environment`

**Critério de Done:**
- Função `rollback_staging_deploy` existe em `render_deploy.py` e bloqueia tentativas em `production`
- Audit event é criado com tipo `"deployment.rollback.staging"`
- Testes cobrem: rollback bem-sucedido, tentativa bloqueada em production, serviço inexistente
- Nenhuma lógica de rollback em outros módulos (consolidação)

**Depende de:** S4

---

## Ordem de Execução Recomendada

```
S1 (Stack Detection)
  └─► S2 (Plan Generation)
        └─► S3 (Execution Gate)
              └─► S4 (Render Deploy + Logs + Healthcheck)
                    └─► S5 (Rollback Staging)
```

Cada slice deve estar com testes passando antes de iniciar o próximo. Slices paralelos não são recomendados neste MVP dado o acoplamento sequencial das interfaces.

---

## Rastreamento

| Slice | Issue | Status |
|---|---|---|
| S1 — Stack Detection | #TBD | Aberto |
| S2 — Plan Generation | #TBD | Aberto |
| S3 — Execution Gate | #TBD | Aberto |
| S4 — Render Deploy | #TBD | Aberto |
| S5 — Rollback Staging | #TBD | Aberto |
