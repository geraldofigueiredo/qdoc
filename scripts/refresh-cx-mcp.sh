#!/bin/bash
# Renova o token do MCP do CX Agent Studio no Claude Code.
# Tokens do GCP expiram em ~1h. Execute este script quando o MCP parar de responder.
#
# Uso: ./scripts/refresh-cx-mcp.sh

set -euo pipefail

MCP_NAME="cx-agent-studio"
MCP_URL="https://ces.googleapis.com/mcp"

echo "Obtendo token GCP..."
TOKEN=$(gcloud auth print-access-token)

if [ -z "$TOKEN" ]; then
  echo "Erro: não foi possível obter o token. Execute: gcloud auth login"
  exit 1
fi

echo "Atualizando MCP '${MCP_NAME}'..."
claude mcp remove "${MCP_NAME}" 2>/dev/null || true
claude mcp add --transport http -s user "${MCP_NAME}" "${MCP_URL}" \
  --header "Authorization: Bearer ${TOKEN}"

echo "MCP '${MCP_NAME}' atualizado com sucesso."
echo "Token válido por ~1 hora. Execute este script novamente quando expirar."
