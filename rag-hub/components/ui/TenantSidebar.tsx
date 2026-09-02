"use client";

import { useCallback, useEffect, useState } from "react";
import type { TenantDocument } from "@/lib/api/multilingualApi";
import { multilingualApi } from "@/lib/api/multilingualApi";
import { FileDropzone } from "./FileDropzone";

interface Props {
  selectedTenant: string | null;
  onSelectTenant: (id: string) => void;
}

const RECORD_TYPE_OPTIONS = [
  "general",
  "faq",
  "help_article",
  "policy",
  "ticket",
  "product_guide",
  "troubleshooting",
] as const;

const typeColors: Record<string, string> = {
  faq: "#00d4aa",
  help_article: "#818cf8",
  policy: "#f59e0b",
  ticket: "#ec4899",
  product_guide: "#3b82f6",
  troubleshooting: "#ef4444",
  general: "#94a3b8",
};

export function TenantSidebar({ selectedTenant, onSelectTenant }: Props) {
  const [tenants, setTenants] = useState<string[]>([]);
  const [documents, setDocuments] = useState<TenantDocument[]>([]);
  const [loading, setLoading] = useState(true);

  const [showAddTenant, setShowAddTenant] = useState(false);
  const [newTenantId, setNewTenantId] = useState("");

  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedRecordType, setSelectedRecordType] = useState("general");
  const [selectedLanguage, setSelectedLanguage] = useState("auto");

  const [error, setError] = useState<string | null>(null);

  const loadTenants = useCallback(async () => {
    try {
      const data = await multilingualApi.listTenants();
      setTenants(data.tenants);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDocuments = useCallback(async (tid: string) => {
    try {
      const data = await multilingualApi.listDocuments(tid);
      setDocuments(data.documents);
    } catch {
      setDocuments([]);
    }
  }, []);

  useEffect(() => {
    loadTenants();
  }, [loadTenants]);

  useEffect(() => {
    if (selectedTenant) loadDocuments(selectedTenant);
    else setDocuments([]);
  }, [selectedTenant, loadDocuments]);

  const handleAddTenant = () => {
    const id = newTenantId.trim();
    if (!id) return;
    setTenants((prev) => (prev.includes(id) ? prev : [...prev, id]));
    onSelectTenant(id);
    setNewTenantId("");
    setShowAddTenant(false);
  };

  const handleDeleteTenant = async (tid: string) => {
    if (!confirm(`Delete ALL documents for tenant "${tid}"?`)) return;
    try {
      await multilingualApi.deleteTenant(tid);
      setTenants((prev) => prev.filter((t) => t !== tid));
      if (selectedTenant === tid) onSelectTenant("");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleDeleteDocument = async (tid: string, docId: string) => {
    if (!confirm("Delete this document?")) return;
    try {
      await multilingualApi.deleteDocument(tid, docId);
      setDocuments((prev) => prev.filter((r) => r.doc_id !== docId));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleUpload = async (files: File[]) => {
    if (!selectedTenant || !files[0]) return;
    setUploading(true);
    setUploadProgress(20);
    setError(null);

    try {
      // Simulate progress increments during upload
      const prog = setInterval(() => {
        setUploadProgress((p) => Math.min(p + 15, 85));
      }, 300);

      const result = await multilingualApi.ingestDocument(files[0], selectedTenant, selectedRecordType, selectedLanguage);
      clearInterval(prog);
      setUploadProgress(100);

      // Add new record to list
      setDocuments((prev) => [
        {
          doc_id: result.doc_id,
          tenant_id: result.tenant_id,
          filename: result.filename,
          doc_type: result.doc_type,
          language: result.language,
          chunks_count: result.chunks_count,
          ingested_at: new Date().toISOString(),
        },
        ...prev,
      ]);

      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
        setShowUpload(false);
      }, 600);
    } catch (e) {
      setError((e as Error).message);
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div
      style={{
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Tenants ({tenants.length})
        </h3>
        <button
          id="add-tenant-btn"
          className="btn btn-ghost btn-sm"
          onClick={() => setShowAddTenant((v) => !v)}
          title="Add tenant"
        >
          {showAddTenant ? "✕" : "+ Add"}
        </button>
      </div>

      {/* Add tenant form */}
      {showAddTenant && (
        <div
          className="animate-fade-in"
          style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6 }}
        >
          <input
            id="new-tenant-id-input"
            className="input"
            placeholder="Tenant ID (e.g. acme_saas)"
            value={newTenantId}
            onChange={(e) => setNewTenantId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddTenant()}
            style={{ flex: 1, fontSize: "0.82rem", padding: "6px 10px" }}
            autoFocus
          />
          <button className="btn btn-primary btn-sm" onClick={handleAddTenant}>
            Add
          </button>
        </div>
      )}

      {/* Tenant list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
        {loading && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", padding: 8 }}>
            Loading…
          </p>
        )}
        {!loading && tenants.length === 0 && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", padding: 8 }}>
            No tenants yet. Add one above.
          </p>
        )}

        {tenants.map((tid) => (
          <div key={tid}>
            {/* Tenant row */}
            <div
              id={`tenant-${tid}`}
              onClick={() => onSelectTenant(tid === selectedTenant ? "" : tid)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                borderRadius: "var(--radius)",
                cursor: "pointer",
                background:
                  selectedTenant === tid ? "var(--accent-dim)" : "transparent",
                border: `1px solid ${
                  selectedTenant === tid ? "var(--accent)" : "transparent"
                }`,
                transition: "all 150ms ease",
                marginBottom: 2,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <span style={{ fontSize: 14 }}>
                  {selectedTenant === tid ? "▾" : "▸"}
                </span>
                <span
                  style={{
                    fontSize: "0.84rem",
                    fontWeight: 500,
                    color:
                      selectedTenant === tid
                        ? "var(--accent)"
                        : "var(--text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {tid}
                </span>
              </div>
              <button
                className="btn btn-danger btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteTenant(tid);
                }}
                title="Delete tenant"
                style={{ padding: "2px 6px", fontSize: "0.72rem" }}
              >
                ✕
              </button>
            </div>

            {/* Records under selected tenant */}
            {selectedTenant === tid && (
              <div
                className="animate-fade-in"
                style={{ paddingLeft: 16, paddingBottom: 8 }}
              >
                {documents.map((rec) => {
                  const color = typeColors[rec.doc_type] ?? "#94a3b8";
                  return (
                    <div
                      key={rec.doc_id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "5px 8px",
                        borderRadius: "var(--radius-sm)",
                        marginBottom: 2,
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                      }}
                    >
                      <div style={{ minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: color,
                            flexShrink: 0,
                          }}
                        />
                        <span
                          style={{
                            fontSize: "0.76rem",
                            color: "var(--text-secondary)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                          title={rec.filename}
                        >
                          {rec.filename} [{rec.language}]
                        </span>
                      </div>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeleteDocument(tid, rec.doc_id)}
                        style={{ padding: "1px 5px", fontSize: "0.66rem", flexShrink: 0 }}
                        title="Delete document"
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}

                {/* Upload toggle */}
                <button
                  id="upload-record-btn"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setShowUpload((v) => !v)}
                  style={{ width: "100%", marginTop: 4 }}
                >
                  {showUpload ? "✕ Cancel" : "+ Upload Support Doc"}
                </button>

                {showUpload && (
                  <div className="animate-fade-in" style={{ marginTop: 8 }}>
                    <select
                      className="input"
                      value={selectedRecordType}
                      onChange={(e) => setSelectedRecordType(e.target.value)}
                      style={{ marginBottom: 8, fontSize: "0.82rem", padding: "6px 10px" }}
                    >
                      {RECORD_TYPE_OPTIONS.map((t) => (
                        <option key={t} value={t}>
                          {t.replace(/_/g, " ")}
                        </option>
                      ))}
                    </select>

                    <input
                      className="input"
                      placeholder="Language (e.g. auto, en, es)"
                      value={selectedLanguage}
                      onChange={(e) => setSelectedLanguage(e.target.value)}
                      style={{ marginBottom: 8, fontSize: "0.82rem", padding: "6px 10px", width: "100%" }}
                    />

                    <FileDropzone
                      onFiles={handleUpload}
                      uploading={uploading}
                      progress={uploadProgress}
                      label="Drop support document"
                      sublabel="PDF, DOCX, TXT, etc."
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Error toast */}
      {error && (
        <div
          className="animate-fade-in"
          style={{
            margin: "8px",
            padding: "8px 12px",
            background: "rgba(248,113,113,0.1)",
            border: "1px solid rgba(248,113,113,0.3)",
            borderRadius: "var(--radius)",
            fontSize: "0.78rem",
            color: "#f87171",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer" }}>✕</button>
        </div>
      )}
    </div>
  );
}
