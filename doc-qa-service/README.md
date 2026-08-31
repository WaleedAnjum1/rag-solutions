# Document Q&A Microservice

A standalone, Ollama-powered RAG microservice. Upload documents and ask natural language questions — from **any project** via a simple REST API.

---

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector Store | ChromaDB (persistent, local) |
| LLM | Ollama (`qwen3:1.7b-q4_K_M` by default) |
| Document Parsing | `pypdf` · `python-docx` · `openpyxl` · plain text / markdown / CSV |

---

## System Prompt & Guardrails

The service implements the **RAG System Prompt Guide** with 9 explicit rules for small quantized local models (such as `qwen3:1.7b-q4_K_M`):

1. **Strict Grounding:** Answers are based ONLY on context passages without outside assumptions.
2. **Standard Refusal & Partial Answers:** Missing context triggers standard refusal (`"I couldn't find relevant information in the provided documents."`), while partial context yields partial answers + missing data flags.
3. **Inline Citations:** Each context block is tagged (`[source: filename.pdf (page X)]`), and answers cite sources inline.
4. **Tabular Reasoning:** `.csv`, `.xlsx`, and `.xls` documents are converted to Markdown tables with header retention across chunks to prevent column misalignment.
5. **Numeric & Literal Fidelity:** Numbers, names, dates, and medical/financial values are quoted verbatim.
6. **Prompt Injection Defense:** Untrusted document text is treated strictly as data, never as system instructions.

---

## Quick Start

```bash
# 1. Clone into your RAG solutions workspace
cd doc-qa-service

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env

# 5. Start the service
python main.py
# or
uvicorn main:app --reload --port 8100
```

Open **http://localhost:8100/docs** for the interactive Swagger UI.

---

## API Reference

### `POST /ingest`
Upload a document to be indexed.

```bash
curl -X POST http://localhost:8100/ingest \
  -F "file=@/path/to/document.pdf" \
  -F "namespace=my-project"
```

**Response:**
```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "document.pdf",
  "namespace": "my-project",
  "chunks_count": 42,
  "message": "Document ingested successfully."
}
```

---

### `POST /query`
Ask a question against ingested documents.

```bash
curl -X POST http://localhost:8100/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the payment terms?", "namespace": "my-project"}'
```

**Response:**
```json
{
  "answer": "Payment is due within 30 days of invoice...",
  "question": "What are the payment terms?",
  "namespace": "my-project",
  "sources": [
    {
      "chunk_id": "550e8400_chunk_3",
      "filename": "document.pdf",
      "text": "Payment terms: Net 30...",
      "relevance_score": 0.91,
      "page": 4,
      "chunk_index": 3
    }
  ],
  "model": "qwen3:1.7b-q4_K_M"
}
```

---

### `POST /query/stream`
Stream the answer token-by-token via SSE.

```bash
curl -X POST http://localhost:8100/query/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarise the contract", "namespace": "my-project"}' \
  --no-buffer
```

Each event:
```
data: {"token": "Payment", "done": false}
data: {"token": " is", "done": false}
...
data: {"sources": [...], "done": true}
```

---

### `GET /documents?namespace=my-project`
List all ingested documents.

### `DELETE /documents/{doc_id}`
Remove a document and all its chunks.

### `GET /health`
Check Ollama, ChromaDB, and embedder status.

---

## Integration Examples

### Laravel (PHP)
```php
use Illuminate\Support\Facades\Http;

// Ingest
Http::attach('file', file_get_contents($path), 'report.pdf')
    ->post('http://localhost:8100/ingest', ['namespace' => 'udharmaster']);

// Query
$res = Http::post('http://localhost:8100/query', [
    'question'  => 'Who has the highest outstanding balance?',
    'namespace' => 'udharmaster',
    'top_k'     => 5,
]);
$answer = $res->json('answer');
```

### JavaScript / Next.js
```js
// Ingest
const form = new FormData();
form.append('file', fileBlob, 'doc.pdf');
form.append('namespace', 'my-project');
await fetch('http://localhost:8100/ingest', { method: 'POST', body: form });

// Query (streaming)
const res = await fetch('http://localhost:8100/query/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ question: 'What is the refund policy?', namespace: 'my-project' }),
});
for await (const chunk of res.body) {
  const line = new TextDecoder().decode(chunk);
  const data = JSON.parse(line.replace('data: ', ''));
  if (!data.done) process.stdout.write(data.token);
}
```

### Python
```python
import httpx

# Ingest
with open("doc.pdf", "rb") as f:
    httpx.post("http://localhost:8100/ingest",
               files={"file": ("doc.pdf", f, "application/pdf")},
               data={"namespace": "research"})

# Query
res = httpx.post("http://localhost:8100/query",
                 json={"question": "What is the conclusion?", "namespace": "research"})
print(res.json()["answer"])
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Generation model |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `CHROMA_DB_PATH` | `./chroma_db` | ChromaDB persistence path |
| `CHUNK_SIZE` | `800` | Characters per chunk |
| `CHUNK_OVERLAP` | `150` | Overlap between chunks |
| `TOP_K` | `5` | Chunks retrieved per query |
| `PORT` | `8100` | Server port |

---

## Namespace Isolation

Each project gets its own isolated vector store collection via `namespace`:

```
namespace: "udharmaster"   → ChromaDB collection: ns_udharmaster
namespace: "voiceclone"    → ChromaDB collection: ns_voiceclone
namespace: "default"       → ChromaDB collection: ns_default
```

Documents in one namespace are never mixed with another.

---

## Supported File Types

| Extension | Parser / Formatter |
|-----------|-------------------|
| `.pdf` | pypdf (with page numbers) |
| `.docx`, `.doc` | python-docx |
| `.xlsx`, `.xls` | openpyxl (Markdown table conversion per sheet) |
| `.csv` | built-in csv module (Markdown table format) |
| `.txt`, `.md`, `.rst` | built-in text parser |

