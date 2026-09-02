"use client";

import { useState } from "react";
import type { PatientSummaryResponse } from "@/lib/types";
import { medicalApi } from "@/lib/api/medicalApi";

interface Props {
  patientId: string;
  onClose: () => void;
}

export function SummaryCard({ patientId, onClose }: Props) {
  const [summary, setSummary] = useState<PatientSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await medicalApi.summarise(patientId);
      setSummary(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  // Trigger load on first render
  if (!summary && !loading && !error) load();

  return (
    /* Backdrop */
    <div
      id="summary-modal-backdrop"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.7)",
        backdropFilter: "blur(6px)",
        zIndex: 50,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      {/* Modal */}
      <div
        className="card animate-slide-up"
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 680,
          maxHeight: "85dvh",
          overflowY: "auto",
          padding: 28,
          position: "relative",
        }}
      >
        {/* Close button */}
        <button
          id="summary-modal-close"
          className="btn btn-ghost btn-sm"
          onClick={onClose}
          style={{ position: "absolute", top: 16, right: 16 }}
        >
          ✕
        </button>

        <div style={{ marginBottom: 20 }}>
          <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>
            Patient Summary
          </p>
          <h2 style={{ color: "var(--accent)" }}>{patientId}</h2>
          <div className="accent-line" style={{ width: 40, marginTop: 8 }} />
        </div>

        {loading && (
          <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-muted)" }}>
            <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
            <p>Generating structured summary…</p>
            <p style={{ fontSize: "0.78rem", marginTop: 4 }}>This may take 10–30 seconds</p>
          </div>
        )}

        {error && (
          <div
            style={{
              padding: "12px 16px",
              background: "rgba(248,113,113,0.1)",
              border: "1px solid rgba(248,113,113,0.25)",
              borderRadius: "var(--radius)",
              color: "#f87171",
              display: "flex",
              gap: 8,
              alignItems: "center",
            }}
          >
            <span>⚠</span>
            <div>
              <p style={{ fontWeight: 600, fontSize: "0.85rem" }}>Summary failed</p>
              <p style={{ fontSize: "0.78rem", marginTop: 2 }}>{error}</p>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={load} style={{ marginLeft: "auto" }}>
              Retry
            </button>
          </div>
        )}

        {summary && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Narrative summary */}
            <Section title="Clinical Overview" icon="📋">
              <p style={{ color: "var(--text-secondary)", lineHeight: 1.7, fontSize: "0.9rem" }}>
                {summary.summary}
              </p>
            </Section>

            {/* Conditions */}
            {summary.conditions.length > 0 && (
              <Section title="Conditions / Diagnoses" icon="🏥">
                <ul style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {summary.conditions.map((c, i) => (
                    <li key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: "0.87rem", color: "var(--text-secondary)" }}>
                      <span style={{ color: "var(--accent)", flexShrink: 0 }}>•</span>
                      {c}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Medications */}
            {summary.medications.length > 0 && (
              <Section title="Medications" icon="💊">
                <ul style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {summary.medications.map((m, i) => (
                    <li key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: "0.87rem", color: "var(--text-secondary)" }}>
                      <span style={{ color: "#818cf8", flexShrink: 0 }}>•</span>
                      {m}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {/* Allergies */}
            {summary.allergies.length > 0 && (
              <Section title="Allergies" icon="⚠️">
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {summary.allergies.map((a, i) => (
                    <span key={i} className="badge badge-warn">{a}</span>
                  ))}
                </div>
              </Section>
            )}

            {/* Last visit */}
            {summary.last_visit && (
              <Section title="Last Visit" icon="📅">
                <p style={{ color: "var(--text-secondary)", fontSize: "0.87rem" }}>
                  {summary.last_visit}
                </p>
              </Section>
            )}

            {/* Model footer */}
            <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              Generated by {summary.model}. For clinical decision support only — not a substitute for professional medical advice.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
        <span>{icon}</span>
        <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
          {title}
        </h3>
      </div>
      <div
        style={{
          background: "var(--bg-elevated)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "14px 16px",
        }}
      >
        {children}
      </div>
    </div>
  );
}
