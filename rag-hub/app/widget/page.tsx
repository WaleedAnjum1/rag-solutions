"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ChatPanel } from "@/components/ui/ChatPanel";
import { useStreamQuery } from "@/lib/hooks/useStreamQuery";
import { medicalApi } from "@/lib/api/medicalApi";
import { docsApi } from "@/lib/api/docsApi";
import { legalPublicApi } from "@/lib/api/legalPublicApi";

function WidgetInner() {
  const params = useSearchParams();
  const service = params.get("service") ?? "docs";
  const patientId = params.get("patientId") ?? "";
  const accent = params.get("accent") ?? (service === "medical" ? "#00d4aa" : service === "legal" ? "#f59e0b" : "#818cf8");

  const { stream, state, reset } = useStreamQuery();

  const handleSend = async (question: string) => {
    if (service === "medical" && patientId) {
      await stream(() => medicalApi.streamQuery(question, patientId));
    } else if (service === "legal") {
      await stream(() => legalPublicApi.streamQuery(question));
    } else {
      await stream(() => docsApi.streamQuery(question));
    }
  };

  return (
    <div
      data-module={service}
      style={{
        height: "100dvh",
        display: "flex",
        flexDirection: "column",
        background: "var(--bg-base)",
        // Inject the accent colour from query param
        // @ts-expect-error CSS custom property
        "--accent": accent,
      }}
    >
      {/* Minimal widget header */}
      <div
        style={{
          padding: "10px 16px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: "var(--bg-surface)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: accent,
            animation: "pulse-dot 2s ease-in-out infinite",
            display: "inline-block",
          }}
        />
        <span style={{ fontSize: "0.84rem", fontWeight: 600, color: "var(--text-primary)" }}>
          {service === "medical" ? "Medical Assistant" : service === "legal" ? "Legal Assistant" : "Document Q&A"}
        </span>
        {patientId && (
          <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginLeft: 4 }}>
            · {patientId}
          </span>
        )}
      </div>

      <div style={{ flex: 1, overflow: "hidden" }}>
        <ChatPanel
          onSend={handleSend}
          streamingAnswer={state.answer}
          streamingSources={state.sources}
          isStreaming={state.isStreaming}
          streamError={state.error}
          onReset={reset}
          emptyTitle="How can I help?"
          emptySubtitle="Ask me anything about the documents"
        />
      </div>
    </div>
  );
}

export default function WidgetPage() {
  return (
    <Suspense fallback={<div style={{ background: "#09090f", height: "100dvh" }} />}>
      <WidgetInner />
    </Suspense>
  );
}
