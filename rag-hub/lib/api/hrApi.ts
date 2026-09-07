export interface HRSource {
  filename: string;
  chunk_index: number;
  relevance_score: number;
  doc_type: string;
}

export interface HRResponse {
  answer: string;
  sources: HRSource[];
}

export interface HRDocument {
  doc_id: string;
  tenant_id: string;
  filename: string;
  doc_type: string;
  language: string;
  chunks_count: number;
  ingested_at: string;
}

export const hrApi = {
  async listTenants(): Promise<{ tenants: string[]; total: number }> {
    const res = await fetch("/api/hr/tenants");
    if (!res.ok) throw new Error("Failed to list tenants");
    return res.json();
  },

  async deleteTenant(tenantId: string) {
    const res = await fetch(`/api/hr/tenants/${tenantId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete tenant");
    return res.json();
  },

  async listDocuments(tenantId: string): Promise<{ documents: HRDocument[]; total: number }> {
    const res = await fetch(`/api/hr/tenants/${tenantId}/documents`);
    if (!res.ok) throw new Error("Failed to list documents");
    return res.json();
  },

  async deleteDocument(tenantId: string, docId: string) {
    const res = await fetch(`/api/hr/tenants/${tenantId}/documents/${docId}`, {
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
  ): Promise<HRDocument> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tenant_id", tenantId);
    formData.append("doc_type", docType);
    formData.append("language", language);

    const res = await fetch("/api/hr/ingest", {
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
      top_k: 5,
    };

    const res = await fetch("/api/hr/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error("Failed to query HR API");
    }

    return res;
  },
};
