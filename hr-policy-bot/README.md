# HR Policy Bot 👔

> **Multi-tenant enterprise HR knowledge retrieval system built on FastAPI, ChromaDB, and local/cloud LLMs.**

---

## 📌 Overview

**HR Policy Bot** is a domain-specialized RAG microservice designed to handle internal company policies, employee handbooks, benefits documentation, and leave entitlements across multiple tenants or company subsidiaries.

### 🌟 Features
- **Multi-Tenant Isolation**: Queries and document ingestion are partitioned per tenant or department namespace.
- **Human-in-the-Loop Escalation**: Automatically checks similarity confidence scores. If the closest policy clause scores below `escalation_min_relevance`, the query is flagged for human HR specialist review.
- **Fast KV Cache**: Re-uses pre-computed LLM context tokens for instant answers on subsequent questions.
- **Hallucination-Proof Grounding**: Strictly requires `[Source N]` citations and refuses answers without sufficient documented backing.

---

## 🚀 Quick Start

### 1. Installation
```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 2. Configuration (`.env`)
```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
EMBEDDING_MODEL=all-MiniLM-L6-v2
ESCALATION_MIN_RELEVANCE=0.45
PORT=8400
```

### 3. Run the Service
```bash
python main.py
```
API runs on `http://localhost:8400` with Swagger docs at `http://localhost:8400/docs`.

---

## 📚 Endpoints

- `POST /tenants/{tenant_id}/ingest`: Ingest HR policies, PDFs, markdown handbooks.
- `POST /tenants/{tenant_id}/query`: Query tenant handbook policies.
- `GET /tenants/{tenant_id}/query/stream`: Server-Sent Events (SSE) query streaming.
- `GET /health`: Health and memory status.

