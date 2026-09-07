import type {
  HealthResponse,
  IngestResponse,
  MedicalQueryResponse,
  PatientSummaryResponse,
  PatientListResponse,
  PatientRecordListResponse,
} from "@/lib/types";

// All calls go through the Next.js proxy at /api/medical/...
// This keeps FastAPI ports hidden from the browser.
const BASE = "/api/medical";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const medicalApi = {
  health: () =>
    fetch(`${BASE}/health`).then((r) => json<HealthResponse>(r)),

  listPatients: () =>
    fetch(`${BASE}/patients/`).then((r) => json<PatientListResponse>(r)),

  listRecords: (patientId: string) =>
    fetch(`${BASE}/patients/${encodeURIComponent(patientId)}/records`).then((r) =>
      json<PatientRecordListResponse>(r)
    ),

  deletePatient: (patientId: string) =>
    fetch(`${BASE}/patients/${encodeURIComponent(patientId)}`, {
      method: "DELETE",
    }).then((r) => json<{ message: string; documents_deleted: number }>(r)),

  deleteRecord: (patientId: string, docId: string) =>
    fetch(
      `${BASE}/patients/${encodeURIComponent(patientId)}/records/${encodeURIComponent(docId)}`,
      { method: "DELETE" }
    ).then((r) => json<{ message: string }>(r)),

  ingest: (file: File, patientId: string, recordType = "general") => {
    const form = new FormData();
    form.append("file", file);
    form.append("patient_id", patientId);
    form.append("record_type", recordType);
    return fetch(`${BASE}/ingest/`, { method: "POST", body: form }).then((r) =>
      json<IngestResponse>(r)
    );
  },

  query: (question: string, patientId: string, topK = 5) =>
    fetch(`${BASE}/query/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, patient_id: patientId, top_k: topK }),
    }).then((r) => json<MedicalQueryResponse>(r)),

  summarise: (patientId: string, topK = 10) =>
    fetch(`${BASE}/query/summarise`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patient_id: patientId, top_k: topK }),
    }).then((r) => json<PatientSummaryResponse>(r)),

  // Returns raw Response for SSE streaming — caller handles the ReadableStream
  streamQuery: (question: string, patientId: string, topK = 5) =>
    fetch(`${BASE}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, patient_id: patientId, top_k: topK }),
    }),
};
