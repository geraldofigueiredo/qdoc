#!/bin/bash
# Configura o MCP do CX Agent Studio com renovação automática de token.
# Execute apenas uma vez. Não é necessário rodar novamente.
#
# Uso: ./scripts/setup-cx-mcp.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE="${SCRIPT_DIR}/cx-mcp-bridge.py"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
MCP_NAME="cx-agent-studio"

echo "Verificando pré-requisitos..."

if ! command -v gcloud &>/dev/null; then
    echo "Erro: gcloud não encontrado. Instale o Google Cloud SDK."
    exit 1
fi
if ! command -v uv &>/dev/null; then
    echo "Erro: uv não encontrado."
    exit 1
fi
if ! command -v claude &>/dev/null; then
    echo "Erro: claude CLI não encontrado."
    exit 1
fi

# Garante que ADC está configurado
if ! gcloud auth application-default print-access-token &>/dev/null 2>&1; then
    echo ""
    echo "Application Default Credentials não encontradas."
    echo "Iniciando login..."
    gcloud auth application-default login
fi

echo "Removendo configuração anterior (se existir)..."
claude mcp remove "${MCP_NAME}" 2>/dev/null || true

echo "Registrando MCP com bridge de renovação automática..."
claude mcp add -s user "${MCP_NAME}" -- \
    uv run --directory "${PROJECT_DIR}" \
    python3 "${BRIDGE}"

echo ""
echo "MCP '${MCP_NAME}' configurado."
echo ""
echo "  Token: gerenciado automaticamente (Application Default Credentials)."
echo "  Renovação: automática, sem intervenção manual."
echo ""
echo "  Próximo passo: reinicie o Claude Code para ativar."
echo "  Se auth quebrar no futuro: gcloud auth application-default login"
