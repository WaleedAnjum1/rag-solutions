"use client";

import { useEffect, useState } from "react";
import type { HealthResponse } from "@/lib/types";

interface Props {
  service: "medical" | "docs";
  label: string;
}

export function HealthBadge({ service, label }: Props) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const res = await fetch(`/api/${service}/health`, { cache: "no-store" });
        if (!cancelled && res.ok) setHealth(await res.json());
      } catch {
        // service unreachable
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    check();
    const interval = setInterval(check, 15_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [service]);

  if (loading) {
    return (
      <span className="badge badge-neutral">
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "var(--text-muted)",
            display: "inline-block",
          }}
        />
        {label}
      </span>
    );
  }

  const ok = health?.status === "ok";

  return (
    <span className={ok ? "badge badge-ok" : "badge badge-error"} title={
      health
        ? `Ollama: ${health.ollama} | ChromaDB: ${health.chromadb} | Model: ${health.ollama_model}`
        : "Service unreachable"
    }>
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: ok ? "var(--accent)" : "#f87171",
          display: "inline-block",
          animation: ok ? "pulse-dot 2s ease-in-out infinite" : "none",
        }}
      />
      {ok ? "Live" : "Offline"}
    </span>
  );
}
