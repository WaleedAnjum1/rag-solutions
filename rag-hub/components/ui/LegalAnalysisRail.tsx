import { useState, useEffect } from "react";
import { legalApi } from "@/lib/api/legalApi";
import { Clause, RiskFlag, DocumentBrief } from "@/lib/types";

export function LegalAnalysisRail({ tenantId, docId, onClose }: { tenantId: string; docId: string; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<"clauses" | "risks" | "brief">("clauses");
  const [clauses, setClauses] = useState<Clause[] | null>(null);
  const [risks, setRisks] = useState<RiskFlag[] | null>(null);
  const [brief, setBrief] = useState<DocumentBrief | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!tenantId || !docId) return;

    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        if (activeTab === "clauses" && !clauses) {
          const res = await legalApi.analyzeClauses(tenantId, docId);
          if (mounted) setClauses(res);
        } else if (activeTab === "risks" && !risks) {
          const res = await legalApi.analyzeRisks(tenantId, docId);
          if (mounted) setRisks(res);
        } else if (activeTab === "brief" && !brief) {
          const res = await legalApi.brief(tenantId, docId);
          if (mounted) setBrief(res);
        }
      } catch (err) {
        if (mounted) setError(String(err));
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => { mounted = false; };
  }, [tenantId, docId, activeTab, clauses, risks, brief]);

  const exportCSV = () => {
    let data: Record<string, unknown>[] = [];
    let filename = "";
    if (activeTab === "clauses" && clauses) {
      data = clauses as unknown as Record<string, unknown>[];
      filename = "clauses.csv";
    } else if (activeTab === "risks" && risks) {
      data = risks as unknown as Record<string, unknown>[];
      filename = "risks.csv";
    }
    if (data.length === 0) return;

    const keys = Object.keys(data[0]);
    const csvContent = [
      keys.join(","),
      ...data.map(row => keys.map(k => `"${String(row[k] || "").replace(/"/g, '""')}"`).join(","))
    ].join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{
      width: 400,
      borderLeft: "1px solid var(--border)",
      background: "var(--bg-surface)",
      display: "flex",
      flexDirection: "column",
      height: "100%",
    }}>
      <div style={{ padding: "16px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Document Analysis</h3>
        <div style={{ display: "flex", gap: "8px" }}>
          {(activeTab === "clauses" || activeTab === "risks") && (
            <button className="btn btn-ghost btn-sm" onClick={exportCSV}>⬇️ CSV</button>
          )}
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
      </div>

      <div style={{ display: "flex", borderBottom: "1px solid var(--border)" }}>
        {(["clauses", "risks", "brief"] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              flex: 1, padding: "12px 0", background: "none", border: "none", cursor: "pointer",
              borderBottom: activeTab === tab ? "2px solid var(--accent)" : "2px solid transparent",
              color: activeTab === tab ? "var(--accent)" : "var(--text-secondary)",
              fontWeight: activeTab === tab ? 600 : 400,
              textTransform: "capitalize"
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
        {loading && <div style={{ color: "var(--text-muted)" }}>Analyzing...</div>}
        {error && <div style={{ color: "#f87171" }}>{error}</div>}

        {!loading && !error && activeTab === "clauses" && clauses && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {clauses.map(c => (
              <div key={c.id} className="card" style={{ padding: "12px" }}>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "4px" }}>
                  {c.clause_type} {c.clause_number ? `· ${c.clause_number}` : ""}
                </div>
                {c.heading && <h4 style={{ margin: "0 0 8px 0" }}>{c.heading}</h4>}
                <p style={{ margin: 0, fontSize: "0.9rem" }}>{c.summary}</p>
              </div>
            ))}
          </div>
        )}

        {!loading && !error && activeTab === "risks" && risks && (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {risks.length === 0 ? (
              <div style={{ color: "var(--text-muted)" }}>No risks identified.</div>
            ) : (
              risks.map(r => (
                <div key={r.id} className="card" style={{ padding: "12px", borderLeft: `4px solid ${r.severity === "high" ? "#f87171" : r.severity === "medium" ? "#fbbf24" : "#3b82f6"}` }}>
                  <h4 style={{ margin: "0 0 4px 0", display: "flex", justifyContent: "space-between" }}>
                    {r.title}
                    <span className={`badge badge-${r.severity === "high" ? "error" : r.severity === "medium" ? "warn" : "neutral"}`}>
                      {r.severity}
                    </span>
                  </h4>
                  <p style={{ margin: "0 0 8px 0", fontSize: "0.9rem" }}>{r.rationale}</p>
                  {r.clause_ref && <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Ref: {r.clause_ref}</div>}
                </div>
              ))
            )}
          </div>
        )}

        {!loading && !error && activeTab === "brief" && brief && (
          <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
            <div>
              <h4 style={{ margin: "0 0 4px 0", color: "var(--text-muted)" }}>Parties</h4>
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.9rem" }}>
                {brief.parties.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
            {brief.effective_date && (
              <div>
                <h4 style={{ margin: "0 0 4px 0", color: "var(--text-muted)" }}>Effective Date</h4>
                <p style={{ margin: 0, fontSize: "0.9rem" }}>{brief.effective_date}</p>
              </div>
            )}
            {brief.term && (
              <div>
                <h4 style={{ margin: "0 0 4px 0", color: "var(--text-muted)" }}>Term</h4>
                <p style={{ margin: 0, fontSize: "0.9rem" }}>{brief.term}</p>
              </div>
            )}
            {brief.governing_law && (
              <div>
                <h4 style={{ margin: "0 0 4px 0", color: "var(--text-muted)" }}>Governing Law</h4>
                <p style={{ margin: 0, fontSize: "0.9rem" }}>{brief.governing_law}</p>
              </div>
            )}
            <div>
              <h4 style={{ margin: "0 0 4px 0", color: "var(--text-muted)" }}>Key Obligations</h4>
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.9rem" }}>
                {brief.key_obligations.map((o, i) => <li key={i}>{o}</li>)}
              </ul>
            </div>
            <div>
              <h4 style={{ margin: "0 0 4px 0", color: "var(--text-muted)" }}>Termination Triggers</h4>
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.9rem" }}>
                {brief.termination_triggers.map((t, i) => <li key={i}>{t}</li>)}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
