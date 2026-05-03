.PHONY: help install up down ingest list sitemap-list sitemap-ingest tui query clear

# Variáveis
DEPTH ?= 10
URL ?= https://docs.cloud.google.com/customer-engagement-ai/conversational-agents/ps
LIMIT ?= 5
SITEMAP_LIMIT ?= 20

help:
	@echo "Comandos disponíveis:"
	@echo "  make install      Instala o qdoc globalmente usando uv"
	@echo "  make up           Sobe o container do Qdrant"
	@echo "  make down         Derruba o container do Qdrant"
	@echo "  make clear        Remove todos os dados do Qdrant"
	@echo "  make ingest       Inicia a ingestão recursiva (padrão: DEPTH=10)"
	@echo "  make list         Apenas lista as URLs recursivas (dry-run)"
	@echo "  make sitemap-list Lista URLs de um sitemap (uso: make sitemap-list SITEMAP=url SITEMAP_LIMIT=20)"
	@echo "  make sitemap-ingest Ingera de um sitemap (uso: make sitemap-ingest SITEMAP=url SITEMAP_LIMIT=20)"
	@echo "  make tui          Inicia a interface TUI"
	@echo "  make query        Testa uma query (uso: make query Q=\"sua busca\" LIMIT=5)"

install:
	uv tool install --force .
	uv run playwright install chromium

setup:
	uv run playwright install chromium

up:
	docker compose up -d

down:
	docker compose down

clear:
	PYTHONPATH=src uv run python -m qdoc.main clear

ingest:
	PYTHONPATH=src uv run python -m qdoc.main ingest --depth $(DEPTH) --url $(URL)

list:
	PYTHONPATH=src uv run python -m qdoc.main ingest --depth $(DEPTH) --url $(URL) --list-only

sitemap-list:
	@if [ -z "$(SITEMAP)" ]; then echo "Erro: Use make sitemap-list SITEMAP=url"; exit 1; fi
	PYTHONPATH=src uv run python -m qdoc.main ingest --sitemap $(SITEMAP) --url $(URL) --list-only --sitemap-limit $(SITEMAP_LIMIT)

sitemap-ingest:
	@if [ -z "$(SITEMAP)" ]; then echo "Erro: Use make sitemap-ingest SITEMAP=url"; exit 1; fi
	PYTHONPATH=src uv run python -m qdoc.main ingest --sitemap $(SITEMAP) --url $(URL) --sitemap-limit $(SITEMAP_LIMIT)

tui:
	PYTHONPATH=src uv run python -m qdoc.main

query:
	@if [ -z "$(Q)" ]; then echo "Erro: Use make query Q=\"sua busca\""; exit 1; fi
	PYTHONPATH=src uv run python -m qdoc.main query "$(Q)" --limit $(LIMIT)

discover:
	@if [ -z "$(P)" ]; then echo "Erro: Use make discover P=\"nome do produto\" QUERY=\"site:url\""; exit 1; fi
	PYTHONPATH=src uv run python -m qdoc.main discover "$(P)" --query "$(QUERY)" --output links.txt
