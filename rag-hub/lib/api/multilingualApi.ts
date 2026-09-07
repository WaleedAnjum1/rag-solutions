export interface MultilingualSource {
  filename: string;
  chunk_index: number;
  relevance_score: number;
  doc_type: string;
}

export interface MultilingualResponse {
  answer: string;
  sources: MultilingualSource[];
}

export interface TenantDocument {
  doc_id: string;
  tenant_id: string;
  filename: string;
  doc_type: string;
  language: string;
  chunks_count: number;
  ingested_at: string;
}

export const multilingualApi = {
  async listTenants(): Promise<{ tenants: string[], total: number }> {
    const res = await fetch("/api/multilingual/tenants");
    if (!res.ok) throw new Error("Failed to list tenants");
    return res.json();
  },

  async deleteTenant(tenantId: string) {
    const res = await fetch(`/api/multilingual/tenants/${tenantId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete tenant");
    return res.json();
  },

  async listDocuments(tenantId: string): Promise<{ documents: TenantDocument[], total: number }> {
    const res = await fetch(`/api/multilingual/tenants/${tenantId}/documents`);
    if (!res.ok) throw new Error("Failed to list documents");
    return res.json();
  },

  async deleteDocument(tenantId: string, docId: string) {
    const res = await fetch(`/api/multilingual/tenants/${tenantId}/documents/${docId}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Failed to delete document");
    return res.json();
  },

  async ingestDocument(
    file: File,
    tenantId: string,
    docType: string,
    language: string = "auto"
  ): Promise<TenantDocument> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tenant_id", tenantId);
    formData.append("doc_type", docType);
    formData.append("language", language);

    const res = await fetch("/api/multilingual/ingest", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("Failed to upload document");
    return res.json();
  },

  async streamQuery(
    question: string,
    tenantId: string,
    language?: string
  ): Promise<Response> {
    const payload: any = {
      tenant_id: tenantId,
      question,
      stream: true,
      top_k: 6,
    };
    if (language) payload.language = language;

    const res = await fetch("/api/multilingual/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error("Failed to query API");
    }

    return res;
  },

  async draftReply(
    message: string,
    tenantId: string,
    tone: string = "friendly",
    language?: string
  ) {
    const payload: any = {
      tenant_id: tenantId,
      message,
      tone,
      top_k: 6,
    };
    if (language) payload.language = language;

    const res = await fetch("/api/multilingual/query/draft-reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error("Failed to draft reply");
    }

    return res.json();
  },
};
