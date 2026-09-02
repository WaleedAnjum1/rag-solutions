"use client";

import { useState } from "react";
import { ModuleHeader } from "@/components/layout/ModuleHeader";
import { PatientSidebar } from "@/components/ui/PatientSidebar";
import { ChatPanel } from "@/components/ui/ChatPanel";
import { SummaryCard } from "@/components/ui/SummaryCard";
import { useStreamQuery } from "@/lib/hooks/useStreamQuery";
import { medicalApi } from "@/lib/api/medicalApi";

const SUGGESTIONS = [
  "What medications is this patient on?",
  "Summarize the latest lab results",
  "Are there any abnormal readings?",
  "What conditions have been diagnosed?",
  "List known allergies",
];

export default function MedicalPage() {
  const [selectedPatient, setSelectedPatient] = useState<string>("");
  const [showSummary, setShowSummary] = useState(false);
  const { stream, state, reset } = useStreamQuery();

  const handleSend = async (question: string) => {
    if (!selectedPatient) return;
    await stream(() =>
      medicalApi.streamQuery(question, selectedPatient)
    );
  };

  const handleSelectPatient = (id: string) => {
    setSelectedPatient(id);
    reset();
  };

  return (
    <div data-module="medical" className="module-layout">
      {/* Top header — spans both columns */}
      <ModuleHeader
        title="Medical Records Q&A"
        subtitle="Patient history · Clinical Q&A · Structured summaries"
        service="medical"
        actions={
          selectedPatient ? (
            <button
              id="generate-summary-btn"
              className="btn btn-ghost btn-sm"
              onClick={() => setShowSummary(true)}
              style={{ borderColor: "var(--accent)", color: "var(--accent)" }}
            >
              📊 Generate Summary
            </button>
          ) : null
        }
      />

      {/* Patient sidebar */}
      <aside style={{ gridRow: 2, overflow: "hidden" }}>
        <PatientSidebar
          selectedPatient={selectedPatient}
          onSelectPatient={handleSelectPatient}
        />
      </aside>

      {/* Chat area */}
      <section style={{ gridRow: 2, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {selectedPatient ? (
          <ChatPanel
            onSend={handleSend}
            streamingAnswer={state.answer}
            streamingSources={state.sources}
            isStreaming={state.isStreaming}
            streamError={state.error}
            onReset={reset}
            suggestions={SUGGESTIONS}
            emptyTitle={`Ask about ${selectedPatient}`}
            emptySubtitle="Upload records using the sidebar, then ask clinical questions"
          />
        ) : (
          <NoPatientSelected />
        )}
      </section>

      {/* Summary modal */}
      {showSummary && selectedPatient && (
        <SummaryCard
          patientId={selectedPatient}
          onClose={() => setShowSummary(false)}
        />
      )}
    </div>
  );
}

function NoPatientSelected() {
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
        🏥
      </div>
      <div>
        <h3 style={{ color: "var(--text-secondary)", marginBottom: 6 }}>
          Select a patient
        </h3>
        <p style={{ fontSize: "0.85rem", maxWidth: 320 }}>
          Choose a patient from the sidebar, or add a new one to start asking
          clinical questions about their records.
        </p>
      </div>
    </div>
  );
}
