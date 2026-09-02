# Multi-Language Customer Support Bot

A standalone, Ollama-powered RAG microservice for customer support. Ingest your help centre once — in whatever language it is already written in — and answer customers in **theirs**, from any application via a simple REST API.

Because retrieval is cross-lingual, a Turkish question is answered from an English help article. You do not have to translate your knowledge base to open a new market.

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
Customer asks (Spanish)        Knowledge base (English)
      │                                 │
      ├── detect language → "es"        │
      ├── embed question ───────────────┤  multilingual embeddings put both
      │                                 │  in the SAME vector space
      ├── retrieve English FAQ chunks ◄─┘
      │
      ├── prompt: [system + English sources] + [question + "Reply in Spanish"]
      │
      └── answer in Spanish, citing [Source 1]
```

Three consequences worth knowing:

1. **One knowledge base, every language.** Content is embedded in its original language; the question is matched semantically, not lexically.
2. **The reply language is decided per request** — detected from the customer's message, or forced with `"language": "de"`.
3. **The cached prompt prefix stays language-neutral.** Ollama's KV cache holds `[system prompt + support content]`; only the question and the reply-language directive are sent fresh. One warm cache therefore serves customers in all languages at once.

---

## System Prompt & Guardrails

Support answers carry commercial and legal weight — a hallucinated refund window is a real liability. The system prompt enforces 12 explicit rules, which come down to nine guarantees:

1. **Strict Grounding:** Answers use only the retrieved support content — never the model's own knowledge of "how refunds usually work".
2. **No Invented Commitments:** The model may not promise a refund, credit, discount, delivery date, or exception the sources do not explicitly grant.
3. **Literal Fidelity:** Prices, timeframes, limits, error codes, and product names are reproduced exactly; currencies and units are never converted.
4. **Inline Citations:** Every factual claim is tagged `[Source N]`, mapped back to a document in the response's `sources` array.
5. **Escalate Instead of Guess:** When the content does not cover the question, the model emits an internal sentinel that the service replaces with a **localised hand-off message** and `escalate: true`. The sentinel is filtered out of SSE streams token-by-token, so it can never appear in a customer's chat window.
6. **Conflict Disclosure:** If two sources disagree, the answer says so and cites both rather than silently picking one.
7. **Privacy:** Internal notes, agent names, ticket IDs, and other customers' data must not be surfaced, even when they appear in an ingested ticket.
8. **Prompt Injection Defense:** Retrieved content is untrusted data, never instructions — relevant here because past tickets contain text customers wrote.
9. **Language Discipline:** The whole reply is written in the requested language, while product names and error codes stay in their original form.

---

## Quick Start

```bash
# 1. Enter the service directory
cd multilingual-support-bot

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

The embedding model (~470 MB) downloads on first use. Run the offline checks any time without Ollama or a model download:

```bash
python test_language.py
```

And the full live flow once the service is up:

```bash
python test_pipeline.py
```

---

## API Reference

### `POST /ingest`
Upload a support document for a workspace.

```bash
curl -X POST http://localhost:8300/ingest \
  -F "file=@/path/to/billing_faq.pdf" \
  -F "tenant_id=acme_saas" \
  -F "doc_type=faq" \
  -F "language=auto"
```

`doc_type`: `faq` · `help_article` · `policy` · `ticket` · `product_guide` · `troubleshooting` · `general`
`language`: a 2-letter code, or `auto` (default) to detect it from the text.

**Response:**
```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "billing_faq.pdf",
  "tenant_id": "acme_saas",
  "doc_type": "faq",
  "language": "en",
  "language_confidence": 0.86,
  "chunks_count": 42,
  "message": "Support document ingested successfully."
}
```

---

### `POST /query`
Answer a customer question. The reply mirrors the customer's language by default.

```bash
curl -X POST http://localhost:8300/query \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "acme_saas", "question": "¿Cuánto tarda un reembolso?"}'
```

**Response:**
```json
{
  "status": "answered",
  "answer": "Los reembolsos se emiten al método de pago original en un plazo de 5 días laborables desde su aprobación [Source 1]...",
  "answer_language": "es",
  "detected_language": "es",
  "language_confidence": 0.62,
  "escalate": false,
  "escalation_reason": null,
  "retrieval_score": 0.87,
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "conversation_id": "chat_7781",
  "sources": [
    { "id": "Source 1", "kind": "faq", "title": "billing_faq.pdf", "page": 2, "language": "en" }
  ],
  "notice": "This reply is generated only from your organisation's support content...",
  "model": "qwen2.5:3b"
}
```

Optional fields: `language` (force the reply language), `doc_type_filter`, `language_filter` (restrict retrieval to source content in one language), `document_id`, `conversation_id`, `top_k`.

---

### `POST /query/stream`
Stream the reply token-by-token via SSE — what a chat widget should use.

```bash
curl -X POST http://localhost:8300/query/stream \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "acme_saas", "question": "Wie storniere ich mein Abo?"}' \
  --no-buffer
```

Each event:
```
data: {"token": "Sie", "done": false}
data: {"token": " können", "done": false}
...
data: {"sources": [...], "answer_language": "de", "escalate": false, "done": true}
```

---

### `POST /query/draft-reply`
Turn an incoming email or ticket into a send-ready draft for a human agent: greeting, grounded answer, closing — in the customer's language.

```bash
curl -X POST http://localhost:8300/query/draft-reply \
  -H "Content-Type: application/json" \
  -d '{
        "tenant_id": "acme_saas",
        "message": "Merhaba, siparişim iki haftadır gelmedi. Ne yapmalıyım?",
        "tone": "friendly"
      }'
```

`tone`: `friendly` (default) · `formal` · `concise`

Unlike `/query`, the response returns the **full source chunks** so the agent can verify each claim before sending.

---

### `GET /tenants`
List all workspaces with ingested content.

### `GET /tenants/{tenant_id}/documents`
List a workspace's documents, newest first, with each document's category and language.

### `DELETE /tenants/{tenant_id}`
Remove all content for a workspace (also clears its caches).

### `DELETE /tenants/{tenant_id}/documents/{doc_id}`
Remove a single document (also evicts it from both caches).

### `GET /languages`
Language codes the service can reply and escalate in — useful for building a language picker.

### `GET /health`
Check Ollama, ChromaDB, and embedder status.

---

## Escalation & Human Hand-off

Every answer carries `escalate` and a machine-readable `escalation_reason`, so a helpdesk can route the conversation without parsing prose:

| `escalation_reason` | Meaning | What to do |
|---------------------|---------|-----------|
| `null` | Grounded answer with a strong match | Send it |
| `no_matching_content` | The workspace has nothing relevant at all | Assign to an agent |
| `not_covered_by_sources` | Content was retrieved but does not answer the question | Assign to an agent; the customer sees a localised hand-off message |
| `low_confidence` | Answered, but the best match scored below `ESCALATION_MIN_RELEVANCE` | Show the draft to an agent before sending |

`low_confidence` still returns the answer — it is a review signal, not a block. Tune the threshold per corpus once you have seen real scores in `retrieval_score`.

---

## Response Latency

Ollama's KV cache is pre-computed per document immediately after ingest, and again in the background after the first query against a document:

| Request | Behaviour |
|---------|-----------|
| First query on a fresh document | Full prompt processed (support content + question) |
| Follow-up queries with `document_id` | **Only the question tokens are processed** — typically a 2-5 second reply |
| Any language | Same warm cache; the language directive travels with the question |

`keep_alive: -1` keeps the model resident, and the model is loaded at startup so the first real customer does not pay for it.

---

## Integration Examples

### Laravel (PHP)
```php
use Illuminate\Support\Facades\Http;

// Ingest a help article
Http::attach('file', file_get_contents($path), 'refund_policy.pdf')
    ->post('http://localhost:8300/ingest', [
        'tenant_id' => 'acme_saas',
        'doc_type'  => 'policy',
        'language'  => 'auto',
    ]);

// Answer a customer, then escalate if the bot is unsure
$res = Http::timeout(120)->post('http://localhost:8300/query', [
    'tenant_id'       => 'acme_saas',
    'question'        => $ticket->body,
    'conversation_id' => $ticket->id,
]);

if ($res->json('escalate')) {
    $ticket->assignToAgent();
} else {
    $ticket->reply($res->json('answer'));
}
```

### JavaScript / Next.js
```js
// Ingest
const form = new FormData();
form.append('file', fileBlob, 'faq.pdf');
form.append('tenant_id', 'acme_saas');
form.append('doc_type', 'faq');
await fetch('http://localhost:8300/ingest', { method: 'POST', body: form });

// Chat widget (streaming)
const res = await fetch('http://localhost:8300/query/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ tenant_id: 'acme_saas', question: userMessage }),
});

const reader = res.body.getReader();
const decoder = new TextDecoder();
for (;;) {
  const { value, done } = await reader.read();
  if (done) break;
  for (const line of decoder.decode(value).split('\n')) {
    if (!line.startsWith('data: ')) continue;
    const event = JSON.parse(line.slice(6));
    if (event.done) {
      if (event.escalate) showHandoffToAgent();
      renderSources(event.sources);
    } else {
      appendToBubble(event.token);
    }
  }
}
```

### Python
```python
import httpx

# Ingest
with open("faq.pdf", "rb") as f:
    httpx.post("http://localhost:8300/ingest",
               files={"file": ("faq.pdf", f, "application/pdf")},
               data={"tenant_id": "acme_saas", "doc_type": "faq"})

# Draft a reply for an agent to review
res = httpx.post("http://localhost:8300/query/draft-reply",
                 json={"tenant_id": "acme_saas",
                       "message": "Quanto tempo demora um reembolso?",
                       "tone": "formal"},
                 timeout=180)
print(res.json()["draft"])
```

---

## Configuration (`.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Generation model |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | **Must be multilingual** — a monolingual model cannot match a Spanish question to an English article |
| `CHROMA_DB_PATH` | `./chroma_db` | ChromaDB persistence path |
| `CHUNK_SIZE` | `700` | Characters per chunk (one chunk ≈ one FAQ answer) |
| `CHUNK_OVERLAP` | `140` | Overlap between chunks |
| `TOP_K` | `6` | Chunks retrieved per query |
| `NUM_CTX` | `8192` | Ollama context window |
| `NUM_PREDICT` | `512` | Max reply tokens |
| `MAX_DOC_CHUNKS` | `20` | Chunks fed to the LLM per document |
| `DEFAULT_ANSWER_LANGUAGE` | `auto` | `auto` mirrors the customer; a code forces every reply |
| `FALLBACK_LANGUAGE` | `en` | Used when detection finds no signal |
| `ESCALATION_MIN_RELEVANCE` | `0.45` | Best-match score below this flags `low_confidence` |
| `PORT` | `8300` | Server port |

---

## Tenant Isolation

Each workspace gets its own ChromaDB collection via `tenant_id`:

```
tenant_id: "acme_saas"   → ChromaDB collection: tn_acme_saas
tenant_id: "telco-eu"    → ChromaDB collection: tn_telco_eu
tenant_id: "shop_mx"     → ChromaDB collection: tn_shop_mx
```

One tenant's support content is never retrieved for another — the isolation that makes per-seat, multi-brand billing safe.

---

## Supported Languages

24 codes are recognised for reply generation, language filtering, and localised escalation messages:

`en` · `es` · `fr` · `de` · `pt` · `it` · `nl` · `pl` · `tr` · `id` · `vi` · `ru` · `uk` · `el` · `ar` · `ur` · `fa` · `he` · `hi` · `bn` · `zh` · `ja` · `ko` · `th`

Call `GET /languages` for the live list. Notes:

- **Detection is a heuristic**, not a classifier: non-Latin scripts are identified by Unicode range (high confidence), Latin scripts by stopword and diacritic scoring (lower confidence, and weaker still on very short messages). If your client already knows the customer's locale, pass `language` explicitly and skip detection entirely.
- The embedding model and the LLM both handle more languages than these 24; this is the set the service can *name in a prompt* and *escalate in*. Add a code plus a translated refusal message to `services/language.py` to extend it.
- Regional tags are normalised: `pt-BR` → `pt`, `zh_Hans` → `zh`.

---

## Supported File Types

| Extension | Parser / Formatter |
|-----------|-------------------|
| `.pdf` | pypdf (with page numbers) |
| `.docx`, `.doc` | python-docx |
| `.xlsx`, `.xls` | openpyxl (Markdown table conversion per sheet) |
| `.csv` | built-in csv module (Markdown table format) |
| `.txt`, `.md`, `.rst` | built-in text parser |

Maximum upload size: 50 MB.
