# Implementation Plan — Legal Document Analyzer

**Status:** planned, not started
**Written:** 2026-09-04
**Scope:** new backend service `legal-doc-analyzer` (port 8500) + `rag-hub` module page + public widget embed for a law-firm website

---

## 1. Objective

One FastAPI service (`legal-doc-analyzer`, port **8500**) that serves **two audiences from the same engine**, plus its `rag-hub` module page and a public widget embed for the law firm's website.

| Audience | Surface | Content | Capability |
|---|---|---|---|
| **Website visitors** (public) | `widget.js` on the firm's site | Firm-curated legal KB: statute summaries, family-law guides, FAQs, blog posts | Ask-only Q&A → grounded answer + citations + disclaimer, escalate to "book a consultation" |
| **Firm staff / paralegals** (private) | `rag-hub` `/legal` page | Uploaded contracts, NDAs, leases, employment agreements | Upload → clause extraction, risk flagging, document brief, Q&A, comparison |

The split is enforced by **separate tenant namespaces**, not by a flag — `VectorStore` already gives one Chroma collection per `tenant_id` (`multilingual-support-bot/services/vectorstore.py:51`), so a visitor question can never retrieve from a client's NDA.

```
firm_public        → statutes, guides, FAQs   (widget reads this, and only this)
matter_<client_id> → that client's contracts  (rag-hub only, never widget)
```

**Assumption stated up front:** visitors ask questions but do **not** upload documents. Visitor upload ("free NDA check" lead magnet) is a different scope — auth, abuse control, retention policy — and is listed as an optional Phase 4.

---

## 2. Base to clone

Clone **`multilingual-support-bot`**, not `doc-qa-service`. It already has everything the legal service needs:

- `tenant_id` namespacing + full tenants CRUD
- escalation machinery (`escalate`, `escalation_reason`, `NO_ANSWER_FOUND` sentinel, `SentinelFilter`) — this *is* the "don't give legal advice you can't source" mechanism, already built
- `POST /query/draft-reply` — becomes "draft client email" for staff
- multilingual embeddings — keep them. A Pakistani firm gets Urdu and English questions against an English corpus, and `paraphrase-multilingual-MiniLM-L12-v2` handles that cross-lingually for free.

Files copied essentially unchanged: `services/embedder.py`, `services/cache.py`, `services/document_loader.py`, `services/language.py`, `services/vectorstore.py` (metadata fields change), `routers/tenants.py`, the `main.py` lifespan/health scaffolding.

---

## 3. Backend — `legal-doc-analyzer/`

```
legal-doc-analyzer/
├── main.py                    # port 8500, lifespan warmup, /health, /taxonomy
├── config.py                  # legal-tuned knobs
├── requirements.txt           # identical to multilingual-support-bot
├── .env.example
├── models/
│   ├── requests.py            # DocType, PracticeArea, ClauseRequest, RiskRequest…
│   └── responses.py           # + Clause, RiskFlag, DocumentBrief
├── routers/
│   ├── ingest.py              # + jurisdiction, practice_area form fields
│   ├── query.py               # /query, /query/stream, /query/draft-email
│   ├── analyze.py             # NEW — clauses, risks, brief, compare
│   └── tenants.py             # copied
└── services/
    ├── clauses.py             # NEW — clause segmentation + risk rules
    ├── rag_chain.py           # legal prompts, disclaimer, analysis chains
    └── … (embedder, cache, document_loader, language, vectorstore copied)
```

### 3.1 `config.py` — what changes from 8300

```python
port: int = 8500
chunk_size: int = 1200          # up from 700 — a clause must not split mid-sentence
chunk_overlap: int = 240
top_k: int = 8                  # legal answers usually need several provisions
num_ctx: int = 8192
num_predict: int = 640          # legal answers are longer than support replies
max_doc_chunks: int = 24
escalation_min_relevance: float = 0.55   # up from 0.45 — a wrong legal answer is a liability
default_jurisdiction: str = "PK"
require_disclaimer: bool = True
```

Chunking is the single most consequential change. Statutes and contracts are structured by numbered clause; 700 chars splits "Section 4 — Termination" away from its sub-clauses and the model cites half a provision.

### 3.2 Taxonomy — `models/requests.py`

Replace the support `DocType` with a legal one, and add two new filterable dimensions. Follow the exact existing idiom (`Literal` + `frozenset(get_args(...))` as the single source of truth for form validation):

```python
DocType = Literal[
    "statute", "case_law", "regulation",        # public KB
    "legal_guide", "faq", "firm_policy",        # public KB
    "contract", "nda", "lease",                 # private matters
    "employment_agreement", "court_filing", "general",
]

PracticeArea = Literal[
    "family",        # marriage, divorce, khula, custody, maintenance
    "child_welfare", # child abuse, guardianship, protection orders
    "property",      # leases, tenancy, transfer
    "corporate",     # NDAs, MOUs, shareholder agreements
    "employment", "criminal", "civil", "tax", "general",
]
```

`jurisdiction` stays a free-form short string (`"PK"`, `"PK-Punjab"`, `"AE"`) rather than an enum — jurisdictions are open-ended and an enum would need a code change per market. Validate as `^[A-Z]{2}(-[A-Za-z ]{2,32})?$`.

Both land in Chroma chunk metadata and become optional query filters, exactly as `doc_type` / `language` already do in `VectorStore.query()`.

### 3.3 `GET /taxonomy`

Mirrors the existing `GET /languages` endpoint. Returns doc types, practice areas, and the jurisdictions actually present in the corpus. The widget uses it to render topic chips ("Family Law", "Tenancy", "NDAs") without hard-coding them in JS.

### 3.4 Prompts — `services/rag_chain.py`

This is where legal differs most from support. Extend `SUPPORT_SYSTEM_PROMPT` into `LEGAL_SYSTEM_PROMPT`, keeping rules 1–8 (source-only, untrusted-sources, cite `[Source N]`, `NO_ANSWER_FOUND` sentinel, verbatim reproduction, conflict disclosure) and adding:

```
- State the governing statute/section by name and number when the sources give one.
- Never state what a court "will" decide, nor predict an outcome, timeline, or cost.
- Never tell the user to take or skip a legal action. Explain what the sources say
  the law provides, then stop.
- If the question depends on facts not in the sources (dates, residence, sect,
  registration status), name the missing fact and reply NO_ANSWER_FOUND.
- If the question concerns immediate danger to a person or child, reply with the
  escalation sentinel — do not attempt an answer.
- Quote statutory language verbatim inside quotation marks. Never paraphrase a
  numbered provision as if it were a quote.
```

Two additions with no equivalent in the existing services:

**Mandatory disclaimer.** `QueryResponse.notice` already exists and is already a fixed non-model string — reuse it verbatim rather than asking the LLM to append a disclaimer (which it will sometimes forget):

> "General information from this firm's published materials, not legal advice. It does not create a lawyer–client relationship. Laws vary by jurisdiction and change over time — speak to a lawyer about your specific situation."

For the SSE path, add `notice` to the existing `final_event(...)` payload in `stream_query`.

**Safety escalation.** A new reason alongside the existing three:

```python
REASON_SAFETY = "safety_referral"   # child abuse / DV / immediate harm
```

Keyword-triggered pre-check *before* retrieval, returning a fixed, non-generated response with helpline contacts from config. A 3B model must not free-generate on a child-abuse disclosure, and `escalation_min_relevance` won't catch it because such a question may well match the child-protection guide with high relevance.

### 3.5 `services/clauses.py` — the analyzer half

`POST /analyze/clauses` → `list[Clause]`. **Deterministic segmentation first, LLM for narration second.** `medical-records-qa` already proves this pattern out: `_extract_readings_regex()` pulls lab values by regex and the LLM only writes prose. Same reasoning applies harder here — qwen2.5:3b is not reliable at emitting valid JSON for 20 clauses, and a hallucinated clause number in a contract review is worse than no review.

```
1. Segment on clause headings — numbering (1., 1.1, Article IV, Section 12),
   ALL-CAPS headings, "WHEREAS"/"NOW THEREFORE" recitals.
2. Classify each segment by keyword/pattern → CLAUSE_TYPES:
   parties, term, termination, payment, confidentiality, non_compete,
   indemnity, liability_cap, governing_law, dispute_resolution,
   force_majeure, assignment, ip_ownership, notice, renewal, penalty, other
3. Per clause, one small LLM call (num_predict≈120) for a plain-language summary,
   grounded strictly in that clause's text.
```

`POST /analyze/risks` → `list[RiskFlag]` with `severity: high|medium|low`, `rationale`, `clause_ref`, `source_id`. Two rule families, both deterministic in their *detection*:

- **Present-but-adverse** — unlimited liability, unilateral amendment/termination, auto-renewal without notice, foreign governing law, perpetual confidentiality, assignment without consent.
- **Missing-clause** — expected clause types absent for the given `doc_type` (an NDA with no term, a lease with no maintenance or deposit-return clause).

The LLM writes the `rationale` from the matched clause text only. Detection stays in code so the risk list is reproducible across runs — which matters if a paralegal is checking it.

`POST /analyze/brief` → `DocumentBrief` (parties, effective date, term, governing law, key obligations, termination triggers, unusual provisions). Structural mirror of medical's `PatientSummaryResponse`.

`POST /analyze/compare` (Phase 3) → clause-type-aligned diff between two `doc_id`s: present in A only, B only, materially different. Backs "how does this NDA differ from our standard template?"

### 3.6 Endpoint summary

| Method | Path | Audience |
|---|---|---|
| `POST` | `/ingest` | Firm |
| `POST` | `/query` · `/query/stream` | **Both** |
| `POST` | `/query/draft-email` | Firm |
| `POST` | `/analyze/clauses` · `/risks` · `/brief` · `/compare` | Firm |
| `GET`/`DELETE` | `/tenants/…` | Firm |
| `GET` | `/taxonomy` · `/health` | Both |

---

## 4. `rag-hub` integration

Follows the `/hr` module exactly — that page is the cleanest template (`app/hr/page.tsx`).

| File | Action |
|---|---|
| `.env.local` | `+ LEGAL_API_URL=http://localhost:8500`, `+ LEGAL_PUBLIC_TENANT=firm_public` |
| `app/api/legal/[...path]/route.ts` | **New** — copy the multilingual proxy verbatim, swap upstream. Staff-only. |
| `app/api/legal-public/[...path]/route.ts` | **New** — hardened public proxy (§5.2) |
| `lib/api/legalApi.ts` | **New** — same shape as `hrApi`, satisfies the existing `TenantApi` interface so `TenantSidebar` works with zero changes; plus `analyzeClauses`, `analyzeRisks`, `brief` |
| `lib/api/legalPublicApi.ts` | **New** — one method: `streamQuery(question, practiceArea?)` |
| `lib/types.ts` | `+ Clause`, `RiskFlag`, `DocumentBrief`, `LegalDocument`; `SSEToken` gains `notice?`, `escalate?`, `escalation_reason?` |
| `app/legal/page.tsx` | **New** — `data-module="legal"`, `ModuleHeader` + `TenantSidebar` + `ChatPanel`, plus a right-hand **Analysis** rail (clauses / risks / brief tabs) |
| `app/globals.css` | `+ [data-module="legal"] { --accent: #f59e0b; … }` — amber, matching the hub card. *Note:* `multilingual` and `hr` blocks are also missing here and silently fall back to teal; worth adding all three in one pass. |
| `app/page.tsx` | Legal card: `href: "/legal"`, `service: "legal"`, `port: ":8500"`, drop `comingSoon` |
| `ModuleHeader.tsx`, `HealthBadge.tsx`, `ModuleCard.tsx` | Add `"legal"` to the three `service` union types |
| `app/widget/page.tsx` | Add the `legal` branch (§5.1) |

Suggestion chips for the page: *"What are the grounds for khula?"* · *"How is child custody decided?"* · *"What notice must a landlord give before eviction?"* · *"Is a non-compete enforceable in my NDA?"* · *"What are a father's maintenance obligations?"*

`TenantSidebar` needs no modification — pass `recordTypeOptions={LEGAL_DOC_TYPES}` and `uploadLabel="Drop contract or legal document"`, as `/hr` already does. Add the legal doc types to its `typeColors` map so the dots aren't all grey.

---

## 5. Widget on the law firm's website

### 5.1 What `widget.js` needs

Three additions to `rag-hub/public/widget.js`:

1. **`data-tenant-id`** — read alongside the existing `data-patient-id`, forwarded as `?tenant=`.
2. **`data-practice-area`** (optional) — lets the firm drop a family-law-scoped bot on its family-law page.
3. **Default accent for `legal`** — `#f59e0b`, matching the hub card. Currently the ternary only special-cases `medical`.

Then in `app/widget/page.tsx`, add the branch:

```tsx
} else if (service === "legal") {
  await stream(() => legalPublicApi.streamQuery(question, practiceArea));
}
```

…plus a persistent one-line disclaimer strip under the header (not a dismissible toast — it must be visible in every screenshot of the widget), and an escalation card rendered when `escalate: true` arrives: *"I can't answer that from our published material — book a consultation."* with the firm's contact link.

The embed the firm pastes before `</body>`:

```html
<script
  src="https://rag.yourfirm.com/widget.js"
  data-service="legal"
  data-tenant-id="firm_public"
  data-practice-area="family"
  data-accent="#f59e0b"
  data-position="bottom-right"
  data-base-url="https://rag.yourfirm.com">
</script>
```

### 5.2 Security — the part that must not be skipped

The existing proxy at `app/api/multilingual/[...path]/route.ts` forwards **every** path and method to upstream with no auth. Reused as-is for legal, anyone who views source on the firm's website learns the base URL and can then `POST /api/legal/ingest` to poison the firm's KB, or `DELETE /api/legal/tenants/firm_public` to wipe it. That's acceptable for a localhost demo and not acceptable on a public law-firm site.

So the public path gets its own proxy, `app/api/legal-public/[...path]/route.ts`:

| Control | Implementation |
|---|---|
| **Method + path allowlist** | Only `POST query/stream` and `GET taxonomy`, `GET health`. Everything else → 404. No `DELETE` export at all. |
| **Server-forced tenant** | Overwrite `tenant_id` in the parsed JSON body from `process.env.LEGAL_PUBLIC_TENANT`. A client-supplied `tenant_id` is discarded, so no visitor can read `matter_*`. |
| **Body clamp** | Reject `question` > 1500 chars; force `top_k` to the server default. |
| **Rate limit** | Per-IP token bucket (in-memory Map is fine at this scale; Redis if multi-instance). ~20 req/5 min. Each miss is a full Ollama generation — this is the DoS surface. |
| **Origin allowlist** | Reject when `Origin`/`Referer` isn't in `LEGAL_ALLOWED_ORIGINS`. Trivially spoofable, but it stops casual reuse of the endpoint. |
| **Iframe embedding** | `next.config.ts` → `headers()` setting `Content-Security-Policy: frame-ancestors https://yourfirm.com` on `/widget`. Without it, any site can iframe the firm's bot. |
| **Network** | Ports 8100–8500 bound to loopback / private network only. FastAPI's `allow_origins=["*"]` is safe *only* because the browser never talks to it directly. |

Staff keep using `/api/legal/*`, which should sit behind whatever auth `rag-hub` gains before it leaves localhost.

---

## 6. Phasing

**Phase 1 — service + public Q&A (the law-firm bot).** Scaffold from `multilingual-support-bot`, legal taxonomy, legal prompts + disclaimer + safety referral, `/ingest`, `/query`, `/query/stream`, `/taxonomy`, tenants. `rag-hub`: proxies, `legalApi`, `/legal` page (chat only), hub card live, accent CSS. Widget: `legal` branch, disclaimer strip, escalation card, hardened public proxy.
*Done when:* a seeded `firm_public` KB answers "What are the grounds for divorce?" with statute citations and a disclaimer, and refuses "Will I win my case?" — from a widget on a separate test HTML page.

**Phase 2 — analyzer (the firm-facing half).** `services/clauses.py`, `/analyze/clauses`, `/analyze/risks`, `/analyze/brief`; Analysis rail in `/legal`.
*Done when:* uploading a sample NDA yields typed clauses with page refs and flags "no term specified" + "perpetual confidentiality" at the right severities.

**Phase 3 — comparison + polish.** `/analyze/compare`, `/query/draft-email`, export clause/risk tables to CSV.

**Phase 4 — optional commercial layer.** Visitor upload for lead-gen (needs email gate, retention policy, size/rate caps), per-document credit metering, lead capture on escalation.

---

## 7. Risks and decisions

| Item | Position |
|---|---|
| **Reproducing statutory text** | Retrieval-only, verbatim quotes, and the corpus is content the firm already publishes. Ingest the firm's own summaries and public statute text — not paywalled reporters. |
| **3B model on legal reasoning** | Acceptable *because* the architecture never asks it to reason — it extracts and quotes, and refuses via sentinel otherwise. Do not raise `temperature` above 0.2, and do not relax `escalation_min_relevance` to reduce refusals. A high refusal rate here is the feature. |
| **Jurisdiction mismatch** | The likeliest real failure: an Indian or US guide in the corpus answering a Pakistani question, since cross-lingual retrieval won't care. Mitigate by making `jurisdiction` mandatory at ingest and defaulting the public widget to `jurisdiction_filter = LEGAL_PUBLIC_JURISDICTION`. |
| **PII in uploaded matters** | Contracts carry names, CNICs, addresses. `matter_*` namespaces stay off the widget path entirely; document a retention/deletion policy since `DELETE /tenants/{id}/documents/{doc_id}` already exists and correctly invalidates both caches. |
| **KV-context prewarm** | The `precompute_ollama_context` fast path is keyed `(tenant, doc_id)` and only engages when `document_id` is supplied. Public widget queries are corpus-wide semantic searches, so they take the slow path by design — that's correct, just don't expect 2–5s replies there. |
| **Chroma registry** | `registry.json` is read-modify-written without a lock. Fine for demo-scale, a real concurrency bug once multiple staff upload simultaneously. Pre-existing across all four services; flagging, not fixing here. |

---

## 8. Verification

1. `curl localhost:8500/health` → `status: ok`, `/taxonomy` → populated.
2. Ingest one guide per practice area into `firm_public`; assert `chunks_count > 0` and correct `jurisdiction` in `GET /tenants/firm_public/documents`.
3. Answer-quality set (~15 questions): family/child-welfare/tenancy/NDA questions → grounded + cited; out-of-scope ("Will I win?", "How much will this cost?") → `escalate: true`; safety question → fixed referral, `reason: safety_referral`.
4. **Isolation test:** ingest into `matter_test`, then query the public endpoint with `tenant_id: "matter_test"` in the body → must answer from `firm_public` and never surface `matter_test` content. This is the single most important test in the plan.
5. Public proxy: `POST /api/legal-public/ingest` → 404. `DELETE /api/legal-public/tenants/firm_public` → 404/405. 25 rapid queries → 429.
6. Analyzer: sample NDA + lease fixtures, assert expected clause types and risk flags.
7. `cd rag-hub && npx tsc --noEmit && npm run lint` — the three `service` union widenings are the likely break.
8. Widget end-to-end from a plain `test-embed.html` on a different origin.

---

## 9. Open decisions

Two choices made rather than asked about — both cheap to revisit before Phase 1 starts:

- **Visitor uploads excluded from v1.** The described use case is ask-only, and upload changes the security model (auth, abuse control, retention). Deferred to Phase 4.
- **Multilingual embeddings retained** (`paraphrase-multilingual-MiniLM-L12-v2`) so Urdu questions hit an English corpus. Swappable for a monolingual model if the corpus and audience are English-only.
