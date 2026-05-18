# AGENTS.md

## Prioridade

Siga esta ordem em todo trabalho:

1. segurança de execução, approval gate e proteção de ambiente
2. compatibilidade com contratos das tools MCP
3. mudanças pequenas, explícitas e testáveis
4. cobertura de testes para regras críticas
5. documentação atualizada quando a verdade do sistema mudar

## Objetivo do Repositório

Este projeto fornece um servidor MCP de orquestração de deploy multi-provider, cobrindo:

- planejamento de deploy (dry-run) com análise de stack e policy
- execução controlada de deploy/migration/rollback com gates
- integrações com providers (Render, Railway, Supabase, Vercel e outros)
- auditoria e redaction para segurança operacional

## Regras de Segurança

- respeitar política por repositório (`policy_result`) antes de executar
- exigir `approval="APPROVED"` para ações mutáveis
- exigir `ci_gate` válido em modo `execute`
- bloquear operações fora do ambiente permitido (staging-first quando aplicável)
- não expor token, secret, URL sensível ou payload não redigido em output

## Convenções de Implementação

- manter retorno estruturado consistente (`ok`, `allowed`, `errors`, `missing_fields`, `audit_event`)
- para operações de execução, centralizar decisão com `evaluate_execution_gate`
- registrar `create_audit_event(...)` em caminhos de allow/block e chamadas críticas
- payloads HTTP explícitos; enviar apenas campos aplicáveis
- manter docstring curta e objetiva em cada tool

## Testes e Qualidade

Toda mudança não trivial deve incluir ou atualizar testes.

- validar comportamento principal e cenários de bloqueio
- para integrações HTTP, usar `httpx.MockTransport`
- para regras críticas, testar negativos (approval ausente, CI gate inválido, policy falhando)
- antes de concluir, rodar:
  - `py -m pytest -q`
  - `py -m ruff check .`

## Git e Fluxo de Trabalho

- não implementar feature nova diretamente em `main`
- usar branch temática (`feat/*`, `fix/*`, `docs/*`)
- preferir commits pequenos e coerentes
- não reverter alterações do usuário sem pedido explícito

## Atualização de Documentação

Quando adicionar/remover tools ou mudar comportamento:

- atualizar `README.md` (seções de tools e status)
- manter `docs/ROADMAP.md` consistente com o código
- atualizar `docs/INTEGRATION.md` quando contrato entre MCPs mudar
- registrar novas regras de segurança relevantes em `docs/SECURITY.md`

## Documentação de Arquitetura e Segurança

Antes de implementar mudanças de segurança, novas tools ou integração, ler:

- `docs/ARCHITECTURE.md` - mapa de módulos e fluxo principal
- `docs/SECURITY.md` - regras e enforcement de segurança
- `docs/INTEGRATION.md` - contrato com `github-unified-mcp`
- `docs/ROADMAP.md` - fases e pendências ativas
