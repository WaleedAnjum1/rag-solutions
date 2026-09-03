"use client";

import Link from "next/link";
import { HealthBadge } from "@/components/ui/HealthBadge";

interface Props {
  title: string;
  subtitle: string;
  service: "medical" | "docs" | "multilingual" | "hr";
  backHref?: string;
  actions?: React.ReactNode;
}

export function ModuleHeader({ title, subtitle, service, backHref = "/", actions }: Props) {
  return (
    <header
      style={{
        gridColumn: "1 / -1",
        background: "var(--bg-surface)",
        borderBottom: "1px solid var(--border)",
        display: "flex",
        alignItems: "center",
        padding: "0 20px",
        gap: 16,
        height: 56,
        flexShrink: 0,
        zIndex: 10,
      }}
    >
      {/* Back link */}
      <Link
        href={backHref}
        style={{
          color: "var(--text-muted)",
          textDecoration: "none",
          fontSize: "0.82rem",
          display: "flex",
          alignItems: "center",
          gap: 4,
          flexShrink: 0,
          transition: "color 150ms ease",
        }}
        onMouseEnter={(e) => ((e.target as HTMLElement).style.color = "var(--accent)")}
        onMouseLeave={(e) => ((e.target as HTMLElement).style.color = "var(--text-muted)")}
      >
        ← Hub
      </Link>

      <span style={{ color: "var(--border-strong)", fontSize: "0.85rem" }}>/</span>

      {/* Title */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                fontSize: "0.92rem",
                fontWeight: 600,
                color: "var(--accent)",
                whiteSpace: "nowrap",
              }}
            >
              {title}
            </span>
            <HealthBadge service={service} label={service} />
          </div>
          <p
            style={{
              fontSize: "0.72rem",
              color: "var(--text-muted)",
              marginTop: 0,
              lineHeight: 1,
            }}
          >
            {subtitle}
          </p>
        </div>
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Slot for page-level actions (e.g. "Generate Summary" button) */}
      {actions}
    </header>
  );
}
