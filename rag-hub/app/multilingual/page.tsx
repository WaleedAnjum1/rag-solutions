"use client";

import { useState } from "react";
import { ModuleHeader } from "@/components/layout/ModuleHeader";
import { TenantSidebar } from "@/components/ui/TenantSidebar";
import { ChatPanel } from "@/components/ui/ChatPanel";
import { useStreamQuery } from "@/lib/hooks/useStreamQuery";
import { multilingualApi } from "@/lib/api/multilingualApi";

const SUGGESTIONS = [
  "How do I reset my password?",
  "What is the refund policy?",
  "Comment annuler mon abonnement?",
  "¿Cuáles son los métodos de pago?",
  "Nasıl iade edebilirim?",
];

export default function MultilingualPage() {
  const [selectedTenant, setSelectedTenant] = useState<string>("");
  const { stream, state, reset } = useStreamQuery();

  const handleSend = async (question: string) => {
    if (!selectedTenant) return;
    await stream(() =>
      multilingualApi.streamQuery(question, selectedTenant)
    );
  };

  const handleSelectTenant = (id: string) => {
    setSelectedTenant(id);
    reset();
  };

  return (
    <div data-module="multilingual" className="module-layout">
      {/* Top header — spans both columns */}
      <ModuleHeader
        title="Multilingual Support Bot"
        subtitle="Global Q&A · Cross-lingual Retrieval · Draft Replies"
        service="multilingual"
      />

      {/* Tenant sidebar */}
      <aside style={{ gridRow: 2, overflow: "hidden" }}>
        <TenantSidebar
          selectedTenant={selectedTenant}
          onSelectTenant={handleSelectTenant}
          api={multilingualApi}
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
            emptySubtitle="Upload support content using the sidebar, then ask questions in any language"
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
        🌍
      </div>
      <div>
        <h3 style={{ color: "var(--text-secondary)", marginBottom: 6 }}>
          Select a workspace
        </h3>
        <p style={{ fontSize: "0.85rem", maxWidth: 320 }}>
          Choose a tenant from the sidebar, or add a new one to start testing 
          multilingual support questions.
        </p>
      </div>
    </div>
  );
}
