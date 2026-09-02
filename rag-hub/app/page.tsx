import type { Metadata } from "next";
import { ModuleCard } from "@/components/ui/ModuleCard";

export const metadata: Metadata = {
  title: "RAG Hub — AI-Powered Document Intelligence",
  description:
    "Unified demo dashboard for RAG-powered AI solutions built on Ollama + ChromaDB. Medical Records Q&A, Document Q&A, and more.",
};

const MODULES = [
  {
    id: "medical",
    href: "/medical",
    service: "medical" as const,
    emoji: "🏥",
    title: "Medical Records Q&A",
    subtitle: "Patient history assistant",
    description:
      "Ingest lab reports, prescriptions, and discharge summaries. Ask clinical questions, get grounded answers, and generate structured patient summaries.",
    accent: "#00d4aa",
    features: ["Per-patient namespaces", "SSE streaming answers", "Structured summaries", "Source citations"],
    port: ":8200",
  },
  {
    id: "docs",
    href: "/docs",
    service: "docs" as const,
    emoji: "📄",
    title: "Document Q&A",
    subtitle: "General document intelligence",
    description:
      "Upload any PDF, DOCX, or TXT document and ask natural language questions. Ideal for contracts, manuals, research papers, and more.",
    accent: "#818cf8",
    features: ["Multi-format upload", "SSE streaming answers", "Namespace isolation", "Source citations"],
    port: ":8100",
  },
  {
    id: "multilingual",
    href: "/multilingual",
    service: "multilingual" as const,
    emoji: "🌍",
    title: "Multilingual Support Bot",
    subtitle: "Global Q&A with cross-lingual retrieval",
    description:
      "Ingest support content in one language and answer customers in any language using cross-lingual vector retrieval.",
    accent: "#3b82f6",
    features: ["Cross-lingual retrieval", "Language detection", "Draft agent replies"],
    port: ":8300",
  },
  {
    id: "legal",
    href: "#",
    service: null,
    emoji: "⚖️",
    title: "Legal Analyzer",
    subtitle: "Contract & clause intelligence",
    description:
      "Upload contracts, NDAs, and leases. Extract clauses, flag risks, and get instant answers from legal documents.",
    accent: "#f59e0b",
    features: ["Risk flagging", "Clause extraction", "Multi-document comparison"],
    port: null,
    comingSoon: true,
  },
  {
    id: "hr",
    href: "#",
    service: null,
    emoji: "👥",
    title: "HR Policy Bot",
    subtitle: "Employee handbook assistant",
    description:
      "Ingest company policies, SOPs, and handbooks. Answer HR queries instantly across your entire organization.",
    accent: "#ec4899",
    features: ["Policy Q&A", "Onboarding assistant", "Slack / Teams ready"],
    port: null,
    comingSoon: true,
  },
];

export default function HubPage() {
  return (
    <main
      style={{
        minHeight: "100dvh",
        padding: "48px 24px",
        maxWidth: 1100,
        margin: "0 auto",
        position: "relative",
        zIndex: 1,
      }}
    >
      {/* Hero */}
      <header style={{ textAlign: "center", marginBottom: 64 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "4px 14px",
            borderRadius: 99,
            background: "rgba(0,212,170,0.08)",
            border: "1px solid rgba(0,212,170,0.2)",
            marginBottom: 20,
            fontSize: "0.78rem",
            fontWeight: 600,
            color: "#00d4aa",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "#00d4aa",
              animation: "pulse-dot 2s ease-in-out infinite",
              display: "inline-block",
            }}
          />
          Live Demo
        </div>

        <h1
          style={{
            background: "linear-gradient(135deg, #f2f2f5 0%, #8b8b9a 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            marginBottom: 16,
            fontSize: "clamp(2rem, 5vw, 3.2rem)",
          }}
        >
          RAG Hub
        </h1>

        <p
          style={{
            color: "var(--text-secondary)",
            fontSize: "1.05rem",
            maxWidth: 520,
            margin: "0 auto",
            lineHeight: 1.65,
          }}
        >
          AI-powered document intelligence built on{" "}
          <span style={{ color: "#00d4aa" }}>Ollama</span> +{" "}
          <span style={{ color: "#818cf8" }}>ChromaDB</span>. Plug into any
          production frontend with a single base URL.
        </p>

        {/* Integration snippet */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            marginTop: 20,
            padding: "8px 16px",
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            fontFamily: "var(--font-mono)",
            fontSize: "0.8rem",
            color: "var(--text-muted)",
          }}
        >
          <span>Base URL:</span>
          <span style={{ color: "var(--text-secondary)" }}>
            http://localhost:3000/api/medical
          </span>
        </div>
      </header>

      {/* Module grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(480px, 1fr))",
          gap: 20,
        }}
      >
        {MODULES.map((mod) => (
          <ModuleCard key={mod.id} {...mod} />
        ))}
      </div>

      {/* Footer */}
      <footer
        style={{
          marginTop: 72,
          textAlign: "center",
          color: "var(--text-muted)",
          fontSize: "0.78rem",
          borderTop: "1px solid var(--border)",
          paddingTop: 24,
          display: "flex",
          flexDirection: "column",
          gap: 4,
        }}
      >
        <p>RAG Hub — Next.js 16 · FastAPI · Ollama · ChromaDB</p>
        <p>
          All answers are grounded in uploaded documents — no hallucinations.
        </p>
      </footer>
    </main>
  );
}
