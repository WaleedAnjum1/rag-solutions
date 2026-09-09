import { LegalDocument, Clause, RiskFlag, DocumentBrief } from "../types";

export interface LegalSource {
  filename: string;
  chunk_index: number;
  relevance_score: number;
  doc_type: string;
}

export interface LegalResponse {
  answer: string;
  sources: LegalSource[];
}

export const legalApi = {
  async listTenants(): Promise<{ tenants: string[]; total: number }> {
    const res = await fetch("/api/legal/tenants");
    if (!res.ok) throw new Error("Failed to list tenants");
    return res.json();
  },

  async deleteTenant(tenantId: string) {
    const res = await fetch(`/api/legal/tenants/${tenantId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete tenant");
    return res.json();
  },

  async listDocuments(tenantId: string): Promise<{ documents: LegalDocument[]; total: number }> {
    const res = await fetch(`/api/legal/tenants/${tenantId}/documents`);
    if (!res.ok) throw new Error("Failed to list documents");
    return res.json();
  },

  async deleteDocument(tenantId: string, docId: string) {
    const res = await fetch(`/api/legal/tenants/${tenantId}/documents/${docId}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete document");
    return res.json();
  },

  async ingestDocument(
    file: File,
    tenantId: string,
    docType: string,
    language: string = "auto"
  ): Promise<LegalDocument> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tenant_id", tenantId);
    formData.append("doc_type", docType);
    formData.append("language", language);

    const res = await fetch("/api/legal/ingest", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to upload document");
    return res.json();
  },

  async streamQuery(question: string, tenantId: string): Promise<Response> {
    const payload = {
      tenant_id: tenantId,
      question,
      stream: true,
      top_k: 8,
    };

    const res = await fetch("/api/legal/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error("Failed to query HR API");
    }

    return res;
  },

  async analyzeClauses(tenantId: string, docId: string): Promise<Clause[]> {
    const res = await fetch("/api/legal/analyze/clauses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: tenantId, doc_id: docId }),
    });
    if (!res.ok) throw new Error("Failed to analyze clauses");
    return res.json();
  },

  async analyzeRisks(tenantId: string, docId: string): Promise<RiskFlag[]> {
    const res = await fetch("/api/legal/analyze/risks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: tenantId, doc_id: docId }),
    });
    if (!res.ok) throw new Error("Failed to analyze risks");
    return res.json();
  },

  async brief(tenantId: string, docId: string): Promise<DocumentBrief> {
    const res = await fetch("/api/legal/analyze/brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: tenantId, doc_id: docId }),
    });
    if (!res.ok) throw new Error("Failed to get brief");
    return res.json();
  },
};
