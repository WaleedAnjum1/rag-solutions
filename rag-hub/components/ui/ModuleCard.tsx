"use client";

import Link from "next/link";
import { HealthBadge } from "@/components/ui/HealthBadge";

export interface ModuleCardProps {
  href: string;
  service: "medical" | "docs" | "multilingual" | "hr" | null;
  emoji: string;
  title: string;
  subtitle: string;
  description: string;
  accent: string;
  features: string[];
  port: string | null;
  comingSoon?: boolean;
}

export function ModuleCard({
  href,
  service,
  emoji,
  title,
  subtitle,
  description,
  accent,
  features,
  port,
  comingSoon,
}: ModuleCardProps) {
  const isActive = !comingSoon;

  const cardContent = (
    <div
      style={{
        background: "var(--bg-surface)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: 28,
        display: "flex",
        flexDirection: "column",
        gap: 16,
        height: "100%",
        transition: "all 200ms ease",
        opacity: comingSoon ? 0.5 : 1,
        cursor: isActive ? "pointer" : "default",
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={(e) => {
        if (!isActive) return;
        const el = e.currentTarget as HTMLElement;
        el.style.borderColor = accent;
        el.style.boxShadow = `0 0 32px ${accent}20`;
        el.style.transform = "translateY(-2px)";
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLElement;
        el.style.borderColor = "var(--border)";
        el.style.boxShadow = "none";
        el.style.transform = "translateY(0)";
      }}
    >
      {/* Accent glow top-right */}
      <div
        style={{
          position: "absolute",
          top: -40,
          right: -40,
          width: 120,
          height: 120,
          borderRadius: "50%",
          background: `${accent}10`,
          filter: "blur(32px)",
          pointerEvents: "none",
        }}
      />

      {/* Header row */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: "var(--radius)",
              background: `${accent}15`,
              border: `1px solid ${accent}30`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22,
              flexShrink: 0,
            }}
          >
            {emoji}
          </div>
          <div>
            <h2 style={{ fontSize: "1.05rem", color: "var(--text-primary)", marginBottom: 2 }}>
              {title}
            </h2>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{subtitle}</p>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          {service && <HealthBadge service={service} label={service} />}
          {port && (
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "0.7rem",
                color: "var(--text-muted)",
              }}
            >
              {port}
            </span>
          )}
          {comingSoon && <span className="badge badge-neutral">Soon</span>}
        </div>
      </div>

      {/* Description */}
      <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", lineHeight: 1.65 }}>
        {description}
      </p>

      {/* Features */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {features.map((f) => (
          <span
            key={f}
            style={{
              padding: "3px 10px",
              borderRadius: 99,
              background: `${accent}10`,
              border: `1px solid ${accent}25`,
              fontSize: "0.72rem",
              color: accent,
              fontWeight: 500,
            }}
          >
            {f}
          </span>
        ))}
      </div>

      {/* CTA */}
      {isActive && (
        <div style={{ marginTop: "auto" }}>
          <div
            className="accent-line"
            style={{
              marginBottom: 12,
              background: `linear-gradient(90deg, ${accent}, transparent)`,
            }}
          />
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: "0.85rem",
              fontWeight: 600,
              color: accent,
            }}
          >
            Open module →
          </span>
        </div>
      )}
    </div>
  );

  if (!isActive) return <div>{cardContent}</div>;
  return (
    <Link href={href} style={{ textDecoration: "none", display: "block" }}>
      {cardContent}
    </Link>
  );
}
