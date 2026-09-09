"use client";

import { useState } from "react";
import { ModuleHeader } from "@/components/layout/ModuleHeader";
import { TenantSidebar } from "@/components/ui/TenantSidebar";
import { ChatPanel } from "@/components/ui/ChatPanel";
import { LegalAnalysisRail } from "@/components/ui/LegalAnalysisRail";
import { useStreamQuery } from "@/lib/hooks/useStreamQuery";
import { legalApi } from "@/lib/api/legalApi";

const SUGGESTIONS = [
  "What are the grounds for khula?",
  "How is child custody decided?",
  "What notice must a landlord give before eviction?",
  "Is a non-compete enforceable in my NDA?",
  "What are a father's maintenance obligations?",
];

const LEGAL_DOC_TYPES = [
  "statute", "case_law", "regulation",
  "legal_guide", "faq", "firm_policy",
  "contract", "nda", "lease",
  "employment_agreement", "court_filing", "general",
] as const;

export default function LegalPage() {
  const [selectedTenant, setSelectedTenant] = useState<string>("");
  const [selectedDocId, setSelectedDocId] = useState<string>("");
  const { stream, state, reset } = useStreamQuery();

  const handleSend = async (question: string) => {
    if (!selectedTenant) return;
    await stream(() => legalApi.streamQuery(question, selectedTenant));
  };

  const handleSelectTenant = (id: string) => {
    setSelectedTenant(id);
    reset();
  };

  return (
    <div data-module="legal" className="module-layout">
      {/* Top header — spans both columns */}
      <ModuleHeader
        title="Legal Document Analyzer"
        subtitle="Contract analysis · Clause extraction · Legal Q&A"
        service="legal"
        actions={
          selectedTenant ? (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => setSelectedDocId(prompt("Enter Document ID to analyze (for testing):") || "")}
              style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
            >
              🔍 Analyze Document
            </button>
          ) : null
        }
      />

      {/* Tenant sidebar */}
      <aside style={{ gridRow: 2, overflow: "hidden" }}>
        <TenantSidebar
          selectedTenant={selectedTenant}
          onSelectTenant={handleSelectTenant}
          api={legalApi}
          recordTypeOptions={LEGAL_DOC_TYPES}
          uploadLabel="Drop contract or legal document"
        />
      </aside>

      {/* Chat area */}
      <section style={{ gridRow: 2, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {selectedTenant ? (
          <ChatPanel
            onSend={handleSend}
            streamingAnswer={state.answer}
            streamingSources={state.sources}
            isStreaming={state.isStreaming}
            streamError={state.error}
            onReset={reset}
            suggestions={SUGGESTIONS}
            emptyTitle={`Ask about ${selectedTenant}`}
            emptySubtitle="Upload legal content using the sidebar, then ask questions about laws, contracts, and clauses."
          />
        ) : (
          <NoTenantSelected />
        )}
      </section>

      {/* Analysis Rail */}
      {selectedTenant && selectedDocId && (
        <LegalAnalysisRail
          tenantId={selectedTenant}
          docId={selectedDocId}
          onClose={() => setSelectedDocId("")}
        />
      )}
    </div>
  );
}

function NoTenantSelected() {
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 14,
        color: "var(--text-muted)",
        padding: 40,
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 64,
          height: 64,
          borderRadius: "var(--radius-lg)",
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 30,
        }}
      >
        👥
      </div>
      <div>
        <h3 style={{ color: "var(--text-secondary)", marginBottom: 6 }}>
          Select a workspace
        </h3>
        <p style={{ fontSize: "0.85rem", maxWidth: 320 }}>
          Choose a company tenant from the sidebar, or add a new one to start
          uploading legal documents and asking questions.
        </p>
      </div>
    </div>
  );
}
