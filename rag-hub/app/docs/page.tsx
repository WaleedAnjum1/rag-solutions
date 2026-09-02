"use client";

import { useCallback, useEffect, useState } from "react";
import { ModuleHeader } from "@/components/layout/ModuleHeader";
import { ChatPanel } from "@/components/ui/ChatPanel";
import { FileDropzone } from "@/components/ui/FileDropzone";
import { useStreamQuery } from "@/lib/hooks/useStreamQuery";
import { docsApi } from "@/lib/api/docsApi";
import type { DocRecord } from "@/lib/types";

const SUGGESTIONS = [
  "What is the main topic of this document?",
  "Summarize the key points",
  "What are the key risks or concerns?",
  "List the main conclusions",
  "What actions are recommended?",
];

export default function DocsPage() {
  const [documents, setDocuments] = useState<DocRecord[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<string | undefined>(undefined);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { stream, state, reset } = useStreamQuery();

  const loadDocuments = useCallback(async () => {
    try {
      const data = await docsApi.listDocuments();
      setDocuments(data.documents ?? []);
    } catch {
      // service may not have GET /documents — ignore gracefully
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleUpload = async (files: File[]) => {
    if (!files[0]) return;
    setUploading(true);
    setUploadProgress(20);
    setUploadError(null);

    try {
      const prog = setInterval(() => {
        setUploadProgress((p) => Math.min(p + 15, 85));
      }, 300);

      const result = await docsApi.ingest(files[0]);
      clearInterval(prog);
      setUploadProgress(100);

      const newDoc: DocRecord = {
        doc_id: result.doc_id,
        filename: result.filename,
        namespace: "",
        chunks_count: result.chunks_count,
        file_type: result.filename.split(".").pop() ?? "",
        ingested_at: new Date().toISOString(),
      };
      setDocuments((prev) => [newDoc, ...prev]);
      setSelectedDoc(result.doc_id);

      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
      }, 600);
    } catch (e) {
      setUploadError((e as Error).message);
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!confirm("Delete this document?")) return;
    try {
      await docsApi.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      if (selectedDoc === docId) setSelectedDoc(undefined);
    } catch {
      // ignore
    }
  };

  const handleSend = async (question: string) => {
    await stream(() => docsApi.streamQuery(question, selectedDoc));
  };

  return (
    <div data-module="docs" className="module-layout">
      <ModuleHeader
        title="Document Q&A"
        subtitle="General document intelligence · PDF · DOCX · TXT"
        service="docs"
      />

      {/* Documents sidebar */}
      <aside
        style={{
          gridRow: 2,
          background: "var(--bg-surface)",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {/* Upload area */}
        <div
          style={{
            padding: 16,
            borderBottom: "1px solid var(--border)",
          }}
        >
          <FileDropzone
            onFiles={handleUpload}
            uploading={uploading}
            progress={uploadProgress}
            label="Upload document"
            sublabel="PDF, DOCX, TXT, MD up to 50 MB"
          />
          {uploadError && (
            <p style={{ fontSize: "0.76rem", color: "#f87171", marginTop: 6 }}>
              ⚠ {uploadError}
            </p>
          )}
        </div>

        {/* Document list */}
        <div style={{ flex: 1, overflowY: "auto", padding: 8 }}>
          {documents.length === 0 && (
            <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", padding: 8, textAlign: "center" }}>
              No documents yet
            </p>
          )}

          {/* "All documents" option */}
          {documents.length > 0 && (
            <button
              onClick={() => setSelectedDoc(undefined)}
              style={{
                width: "100%",
                padding: "7px 10px",
                borderRadius: "var(--radius)",
                background: selectedDoc === undefined ? "var(--accent-dim)" : "transparent",
                border: `1px solid ${selectedDoc === undefined ? "var(--accent)" : "transparent"}`,
                color: selectedDoc === undefined ? "var(--accent)" : "var(--text-secondary)",
                fontSize: "0.82rem",
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                marginBottom: 4,
                transition: "all 150ms ease",
              }}
            >
              🗂 All documents
            </button>
          )}

          {documents.map((doc) => (
            <div
              key={doc.doc_id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "7px 10px",
                borderRadius: "var(--radius)",
                background:
                  selectedDoc === doc.doc_id ? "var(--accent-dim)" : "transparent",
                border: `1px solid ${
                  selectedDoc === doc.doc_id ? "var(--accent)" : "transparent"
                }`,
                cursor: "pointer",
                marginBottom: 2,
                transition: "all 150ms ease",
              }}
              onClick={() => setSelectedDoc(doc.doc_id)}
            >
              <div style={{ minWidth: 0 }}>
                <p
                  style={{
                    fontSize: "0.82rem",
                    fontWeight: 500,
                    color:
                      selectedDoc === doc.doc_id
                        ? "var(--accent)"
                        : "var(--text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                  title={doc.filename}
                >
                  {doc.filename}
                </p>
                <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 1 }}>
                  {doc.chunks_count} chunks
                </p>
              </div>
              <button
                className="btn btn-danger btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteDoc(doc.doc_id);
                }}
                style={{ padding: "2px 6px", fontSize: "0.72rem", flexShrink: 0, marginLeft: 6 }}
                title="Delete document"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </aside>

      {/* Chat area */}
      <section style={{ gridRow: 2, overflow: "hidden" }}>
        <ChatPanel
          onSend={handleSend}
          streamingAnswer={state.answer}
          streamingSources={state.sources}
          isStreaming={state.isStreaming}
          streamError={state.error}
          onReset={reset}
          suggestions={SUGGESTIONS}
          emptyTitle="Ask about your documents"
          emptySubtitle={
            documents.length === 0
              ? "Upload a document to get started"
              : "Select a document or ask across all"
          }
        />
      </section>
    </div>
  );
}
