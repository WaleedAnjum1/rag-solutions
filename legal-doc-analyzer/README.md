# Legal Document Analyzer

A standalone, Ollama-powered RAG microservice for legal document analysis. Ingest your legal corpus once — in whatever language it is already written in — and analyze case files, laws, and legal documents in **your** language, from any application via a simple REST API.

Because retrieval is cross-lingual, a Turkish question is answered from an English legal document. You do not have to translate your case files to work across different jurisdictions.

---

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Embeddings | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (50+ languages, one shared vector space) |
| Vector Store | ChromaDB (persistent, local, one collection per tenant) |
| LLM | Ollama (`qwen2.5:3b` by default — strong multilingual output for its size) |
| Language Detection | Unicode script counting + stopword scoring (no extra dependency) |
| Document Parsing | `pypdf` · `python-docx` · `openpyxl` · plain text / markdown / CSV |

---

## How Cross-Lingual Answering Works

```
Lawyer asks (Spanish)           Case Files (English)
      │                                 │
      ├── detect language → "es"        │
      ├── embed question ───────────────┤  multilingual embeddings put both
      │                                 │  in the SAME vector space
      ├── retrieve English legal chunks◄─┘
      │
      ├── prompt: [system + English sources] + [question + "Reply in Spanish"]
      │
      └── answer in Spanish, citing [Source 1]
```

Three consequences worth knowing:

1. **One knowledge base, every language.** Content is embedded in its original language; the question is matched semantically, not lexically.
2. **The reply language is decided per request** — detected from the user's message, or forced with `"language": "de"`.
3. **The cached prompt prefix stays language-neutral.** Ollama's KV cache holds `[system prompt + legal content]`; only the question and the reply-language directive are sent fresh.

---

## System Prompt & Guardrails

Legal analysis carries significant weight — hallucinated laws or precedents are a real liability. The system prompt enforces strict rules:

1. **Strict Grounding:** Answers use only the retrieved legal content — never the model's own knowledge.
2. **Literal Fidelity:** Dates, fines, codes, and legal terms are reproduced exactly.
3. **Inline Citations:** Every factual claim is tagged `[Source N]`, mapped back to a document in the response's `sources` array.
4. **Conflict Disclosure:** If two sources disagree (e.g., conflicting laws), the answer says so and cites both.
5. **Language Discipline:** The whole reply is written in the requested language, while legal codes and proper nouns stay in their original form.

---

## Quick Start

```bash
# 1. Enter the service directory
cd legal-doc-analyzer

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env

# 5. Pull the generation model (once)
ollama pull qwen2.5:3b

# 6. Start the service
python main.py
# or
uvicorn main:app --reload --port 8300
```

Open **http://localhost:8300/docs** for the interactive Swagger UI.

---

## Legal References & Examples

This tool can be used to index and analyze various complex international legal frameworks, including:

- **Hate Crimes:** Analyze the variations in bias-motivated crimes globally, such as the distinct treatment of hate speech in the U.S. versus the criminalization of public incitement in the EU, or Canada's specific sentencing enhancements for sexual orientation.
- **Divorce and Marital Abuse Laws:** Track the shift towards "no-fault" divorce systems, the expanding legal definition of domestic abuse (including psychological and financial abuse or "coercive control"), and the critical impact of documented abuse on child custody and asset division in international jurisdictions.

**Useful Resources:**
- [Hate Crime Laws in the US (Justice.gov)](https://www.justice.gov/hatecrimes/laws-and-policies)
- [European Commission on Combating Hate Crime](https://commission.europa.eu/strategy-and-policy/policies/justice-and-fundamental-rights/combatting-discrimination/racism-and-xenophobia/combating-hate-speech-and-hate-crime_en)
- [Divorce and Domestic Violence Overview (Justia)](https://www.justia.com/family/divorce/domestic-violence-and-divorce/)
- [Global Perspectives on Marital Abuse (World Bank)](https://www.worldbank.org/en/topic/socialdevelopment)

You can find a sample ingestion document in `sample_legal_doc.md`.

---

## API Reference

### `POST /ingest`
Upload a legal document for a workspace.

```bash
curl -X POST http://localhost:8300/ingest \
  -F "file=@/path/to/case_file.pdf" \
  -F "tenant_id=lawfirm_alpha" \
  -F "doc_type=case_file" \
  -F "language=auto"
```

### `POST /query`
Answer a legal question based on ingested documents.

```bash
curl -X POST http://localhost:8300/query \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "lawfirm_alpha", "question": "¿Cuáles son los precedentes en este caso?"}'
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Generation model |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Multilingual matching |
| `CHROMA_DB_PATH` | `./chroma_db` | ChromaDB persistence path |
| `PORT` | `8300` | Server port |

---

## Supported File Types

| Extension | Parser / Formatter |
|-----------|-------------------|
| `.pdf` | pypdf (with page numbers) |
| `.docx`, `.doc` | python-docx |
| `.xlsx`, `.xls` | openpyxl |
| `.csv` | built-in csv module |
| `.txt`, `.md`, `.rst` | built-in text parser |
