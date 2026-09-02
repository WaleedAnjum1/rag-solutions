"use client";

import type { Source } from "@/lib/types";

interface Props {
  sources: Source[];
}

const kindColors: Record<string, string> = {
  lab_report: "#00d4aa",
  prescription: "#818cf8",
  discharge_summary: "#f59e0b",
  imaging: "#ec4899",
  consultation_note: "#34d399",
  general: "#94a3b8",
  report: "#818cf8",
  document: "#94a3b8",
};

export function SourceCitations({ sources }: Props) {
  if (!sources.length) return null;

  return (
    <div
      className="animate-fade-in"
      style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}
    >
      <p
        style={{
          fontSize: "0.72rem",
          fontWeight: 600,
          color: "var(--text-muted)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        Sources
      </p>

      {sources.map((src, i) => {
        const color = kindColors[src.kind] ?? "#94a3b8";
        return (
          <div
            key={src.id ?? i}
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderLeft: `3px solid ${color}`,
              borderRadius: "var(--radius)",
              padding: "10px 14px",
              display: "flex",
              alignItems: "flex-start",
              gap: 10,
            }}
          >
            {/* Citation number */}
            <span
              style={{
                flexShrink: 0,
                width: 20,
                height: 20,
                borderRadius: "50%",
                background: `${color}22`,
                border: `1px solid ${color}44`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "0.68rem",
                fontWeight: 700,
                color,
                fontFamily: "var(--font-mono)",
              }}
            >
              {i + 1}
            </span>

            <div style={{ minWidth: 0 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  flexWrap: "wrap",
                }}
              >
                <span
                  style={{
                    fontSize: "0.82rem",
                    fontWeight: 600,
                    color: "var(--text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    maxWidth: 240,
                  }}
                >
                  {src.title}
                </span>

                <span
                  className="badge"
                  style={{
                    background: `${color}18`,
                    color,
                    border: `1px solid ${color}33`,
                    fontSize: "0.66rem",
                  }}
                >
                  {src.kind.replace(/_/g, " ")}
                </span>

                {src.page != null && (
                  <span style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                    p.{src.page}
                  </span>
                )}
              </div>

              {src.url && (
                <a
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: "0.75rem",
                    color,
                    textDecoration: "none",
                    marginTop: 2,
                    display: "inline-block",
                  }}
                >
                  ↗ View source
                </a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
