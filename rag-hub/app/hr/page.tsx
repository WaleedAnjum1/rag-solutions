"use client";

import { useState } from "react";
import { ModuleHeader } from "@/components/layout/ModuleHeader";
import { TenantSidebar } from "@/components/ui/TenantSidebar";
import { ChatPanel } from "@/components/ui/ChatPanel";
import { useStreamQuery } from "@/lib/hooks/useStreamQuery";
import { hrApi } from "@/lib/api/hrApi";

const SUGGESTIONS = [
  "What is the remote work policy?",
  "How many days of PTO do I get per year?",
  "How do I submit an expense reimbursement?",
  "What are the core working hours?",
  "What is the process for requesting parental leave?",
];

const HR_DOC_TYPES = [
  "general",
  "policy",
  "handbook",
  "sop",
  "onboarding",
  "benefits",
  "compliance",
] as const;

export default function HRPage() {
  const [selectedTenant, setSelectedTenant] = useState<string>("");
  const { stream, state, reset } = useStreamQuery();

  const handleSend = async (question: string) => {
    if (!selectedTenant) return;
    await stream(() => hrApi.streamQuery(question, selectedTenant));
  };

  const handleSelectTenant = (id: string) => {
    setSelectedTenant(id);
    reset();
  };

  return (
    <div data-module="hr" className="module-layout">
      {/* Top header — spans both columns */}
      <ModuleHeader
        title="HR Policy & Onboarding Bot"
        subtitle="Employee handbook assistant · Policy Q&A · Onboarding docs"
        service="hr"
      />

      {/* Tenant sidebar */}
      <aside style={{ gridRow: 2, overflow: "hidden" }}>
        <TenantSidebar
          selectedTenant={selectedTenant}
          onSelectTenant={handleSelectTenant}
          api={hrApi}
          recordTypeOptions={HR_DOC_TYPES}
          uploadLabel="Drop HR document"
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
            emptySubtitle="Upload HR content using the sidebar, then ask questions about policies, benefits, and procedures"
          />
        ) : (
          <NoTenantSelected />
        )}
      </section>
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
          uploading HR documents and asking questions.
        </p>
      </div>
    </div>
  );
}
