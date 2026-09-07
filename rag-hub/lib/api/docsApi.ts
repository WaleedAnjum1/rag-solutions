import type {
  HealthResponse,
  IngestResponse,
  DocQueryResponse,
  DocListResponse,
} from "@/lib/types";

const BASE = "/api/docs";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const docsApi = {
  health: () =>
    fetch(`${BASE}/health`).then((r) => json<HealthResponse>(r)),

  listDocuments: () =>
    fetch(`${BASE}/documents/`).then((r) => json<DocListResponse>(r)),

  deleteDocument: (docId: string) =>
    fetch(`${BASE}/documents/${encodeURIComponent(docId)}`, {
      method: "DELETE",
    }).then((r) => json<{ message: string }>(r)),

  ingest: (file: File, namespace?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (namespace) form.append("namespace", namespace);
    return fetch(`${BASE}/ingest/`, { method: "POST", body: form }).then((r) =>
      json<IngestResponse>(r)
    );
  },

  query: (question: string, documentId?: string, topK = 5) =>
    fetch(`${BASE}/query/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, document_id: documentId, top_k: topK }),
    }).then((r) => json<DocQueryResponse>(r)),

  streamQuery: (question: string, documentId?: string, topK = 5) =>
    fetch(`${BASE}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, document_id: documentId, top_k: topK }),
    }),
};
