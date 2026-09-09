// Shared API types — exactly matching the FastAPI response schemas

export interface HealthResponse {
  status: "ok" | "degraded";
  ollama: string;
  chromadb: string;
  embedding_model: string;
  ollama_model: string;
}

// ─── Medical Records QA ──────────────────────────────────────────────────────

export interface IngestResponse {
  doc_id: string;
  filename: string;
  patient_id: string;
  record_type: string;
  chunks_count: number;
  message?: string;
}

export interface Source {
  id: string;
  kind: string;
  title: string;
  page?: number | null;
  url?: string | null;
}

export interface Reading {
  name: string;
  value: string;
  unit: string;
  reference_range: string;
  result_type: string;
  status: string;
  note: string;
  source_id: string;
}

export interface MedicalQueryResponse {
  status: string;
  answer: string;
  document_id?: string | null;
  conversation_id?: string | null;
  readings: Reading[];
  sources: Source[];
  notice: string;
  question?: string | null;
  patient_id?: string | null;
  model?: string | null;
}

export interface PatientSummaryResponse {
  patient_id: string;
  summary: string;
  conditions: string[];
  medications: string[];
  allergies: string[];
  last_visit?: string | null;
  sources: SourceChunk[];
  model: string;
}

export interface SourceChunk {
  chunk_id: string;
  doc_id: string;
  filename: string;
  text: string;
  relevance_score?: number | null;
  page?: number | null;
  chunk_index: number;
  record_type?: string | null;
}

export interface PatientRecord {
  doc_id: string;
  patient_id: string;
  filename: string;
  record_type: string;
  chunks_count: number;
  ingested_at: string;
}

export interface PatientRecordListResponse {
  patient_id: string;
  records: PatientRecord[];
  total: number;
}

export interface PatientListResponse {
  patients: string[];
  total: number;
}

// ─── Doc QA Service ───────────────────────────────────────────────────────────

export interface DocQueryResponse {
  status: string;
  answer: string;
  sources: Source[];
  question?: string | null;
  model?: string | null;
}

export interface DocRecord {
  doc_id: string;
  filename: string;
  namespace: string;
  chunks_count: number;
  file_type: string;
  ingested_at: string;
}

export interface DocListResponse {
  documents: DocRecord[];
  total: number;
}

// ─── SSE streaming ────────────────────────────────────────────────────────────

export interface SSEToken {
  token?: string;
  done: boolean;
  sources?: Source[];
  error?: string;
  notice?: string;
  escalate?: boolean;
  escalation_reason?: string;
}

// ─── Legal Document Analyzer ──────────────────────────────────────────────────

export interface Clause {
  id: string;
  clause_number?: string | null;
  heading?: string | null;
  text: string;
  clause_type: string;
  summary: string;
  page?: number | null;
}

export interface RiskFlag {
  id: string;
  severity: "high" | "medium" | "low";
  title: string;
  rationale: string;
  clause_ref?: string | null;
  source_id?: string | null;
}

export interface DocumentBrief {
  doc_id: string;
  parties: string[];
  effective_date?: string | null;
  term?: string | null;
  governing_law?: string | null;
  key_obligations: string[];
  termination_triggers: string[];
  unusual_provisions: string[];
}

export interface LegalDocument {
  doc_id: string;
  tenant_id: string;
  filename: string;
  doc_type: string;
  practice_area?: string;
  jurisdiction?: string;
  language: string;
  chunks_count: number;
  ingested_at: string;
}
