"use client";

import { useCallback, useEffect, useState } from "react";
import type { PatientRecord } from "@/lib/types";
import { medicalApi } from "@/lib/api/medicalApi";
import { FileDropzone } from "./FileDropzone";

interface Props {
  selectedPatient: string | null;
  onSelectPatient: (id: string) => void;
}

const RECORD_TYPE_OPTIONS = [
  "general",
  "lab_report",
  "prescription",
  "discharge_summary",
  "imaging",
  "consultation_note",
] as const;

const typeColors: Record<string, string> = {
  lab_report: "#00d4aa",
  prescription: "#818cf8",
  discharge_summary: "#f59e0b",
  imaging: "#ec4899",
  consultation_note: "#34d399",
  general: "#94a3b8",
};

export function PatientSidebar({ selectedPatient, onSelectPatient }: Props) {
  const [patients, setPatients] = useState<string[]>([]);
  const [records, setRecords] = useState<PatientRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const [showAddPatient, setShowAddPatient] = useState(false);
  const [newPatientId, setNewPatientId] = useState("");

  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedRecordType, setSelectedRecordType] = useState("general");

  const [error, setError] = useState<string | null>(null);

  const loadPatients = useCallback(async () => {
    try {
      const data = await medicalApi.listPatients();
      setPatients(data.patients);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRecords = useCallback(async (pid: string) => {
    try {
      const data = await medicalApi.listRecords(pid);
      setRecords(data.records);
    } catch {
      setRecords([]);
    }
  }, []);

  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  useEffect(() => {
    if (selectedPatient) loadRecords(selectedPatient);
    else setRecords([]);
  }, [selectedPatient, loadRecords]);

  const handleAddPatient = () => {
    const id = newPatientId.trim();
    if (!id) return;
    setPatients((prev) => (prev.includes(id) ? prev : [...prev, id]));
    onSelectPatient(id);
    setNewPatientId("");
    setShowAddPatient(false);
  };

  const handleDeletePatient = async (pid: string) => {
    if (!confirm(`Delete ALL records for patient "${pid}"?`)) return;
    try {
      await medicalApi.deletePatient(pid);
      setPatients((prev) => prev.filter((p) => p !== pid));
      if (selectedPatient === pid) onSelectPatient("");
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleDeleteRecord = async (pid: string, docId: string) => {
    if (!confirm("Delete this record?")) return;
    try {
      await medicalApi.deleteRecord(pid, docId);
      setRecords((prev) => prev.filter((r) => r.doc_id !== docId));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleUpload = async (files: File[]) => {
    if (!selectedPatient || !files[0]) return;
    setUploading(true);
    setUploadProgress(20);
    setError(null);

    try {
      // Simulate progress increments during upload
      const prog = setInterval(() => {
        setUploadProgress((p) => Math.min(p + 15, 85));
      }, 300);

      const result = await medicalApi.ingest(files[0], selectedPatient, selectedRecordType);
      clearInterval(prog);
      setUploadProgress(100);

      // Add new record to list
      setRecords((prev) => [
        {
          doc_id: result.doc_id,
          patient_id: result.patient_id,
          filename: result.filename,
          record_type: result.record_type,
          chunks_count: result.chunks_count,
          ingested_at: new Date().toISOString(),
        },
        ...prev,
      ]);

      setTimeout(() => {
        setUploading(false);
        setUploadProgress(0);
        setShowUpload(false);
      }, 600);
    } catch (e) {
      setError((e as Error).message);
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div
      style={{
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h3 style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Patients ({patients.length})
        </h3>
        <button
          id="add-patient-btn"
          className="btn btn-ghost btn-sm"
          onClick={() => setShowAddPatient((v) => !v)}
          title="Add patient"
        >
          {showAddPatient ? "✕" : "+ Add"}
        </button>
      </div>

      {/* Add patient form */}
      {showAddPatient && (
        <div
          className="animate-fade-in"
          style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6 }}
        >
          <input
            id="new-patient-id-input"
            className="input"
            placeholder="Patient ID (e.g. PT-001)"
            value={newPatientId}
            onChange={(e) => setNewPatientId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddPatient()}
            style={{ flex: 1, fontSize: "0.82rem", padding: "6px 10px" }}
            autoFocus
          />
          <button className="btn btn-primary btn-sm" onClick={handleAddPatient}>
            Add
          </button>
        </div>
      )}

      {/* Patient list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "8px" }}>
        {loading && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", padding: 8 }}>
            Loading…
          </p>
        )}
        {!loading && patients.length === 0 && (
          <p style={{ color: "var(--text-muted)", fontSize: "0.8rem", padding: 8 }}>
            No patients yet. Add one above.
          </p>
        )}

        {patients.map((pid) => (
          <div key={pid}>
            {/* Patient row */}
            <div
              id={`patient-${pid}`}
              onClick={() => onSelectPatient(pid === selectedPatient ? "" : pid)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                borderRadius: "var(--radius)",
                cursor: "pointer",
                background:
                  selectedPatient === pid ? "var(--accent-dim)" : "transparent",
                border: `1px solid ${
                  selectedPatient === pid ? "var(--accent)" : "transparent"
                }`,
                transition: "all 150ms ease",
                marginBottom: 2,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <span style={{ fontSize: 14 }}>
                  {selectedPatient === pid ? "▾" : "▸"}
                </span>
                <span
                  style={{
                    fontSize: "0.84rem",
                    fontWeight: 500,
                    color:
                      selectedPatient === pid
                        ? "var(--accent)"
                        : "var(--text-primary)",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {pid}
                </span>
              </div>
              <button
                className="btn btn-danger btn-sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeletePatient(pid);
                }}
                title="Delete patient"
                style={{ padding: "2px 6px", fontSize: "0.72rem" }}
              >
                ✕
              </button>
            </div>

            {/* Records under selected patient */}
            {selectedPatient === pid && (
              <div
                className="animate-fade-in"
                style={{ paddingLeft: 16, paddingBottom: 8 }}
              >
                {records.map((rec) => {
                  const color = typeColors[rec.record_type] ?? "#94a3b8";
                  return (
                    <div
                      key={rec.doc_id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "5px 8px",
                        borderRadius: "var(--radius-sm)",
                        marginBottom: 2,
                        background: "var(--bg-elevated)",
                        border: "1px solid var(--border)",
                      }}
                    >
                      <div style={{ minWidth: 0, display: "flex", alignItems: "center", gap: 6 }}>
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: color,
                            flexShrink: 0,
                          }}
                        />
                        <span
                          style={{
                            fontSize: "0.76rem",
                            color: "var(--text-secondary)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                          title={rec.filename}
                        >
                          {rec.filename}
                        </span>
                      </div>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeleteRecord(pid, rec.doc_id)}
                        style={{ padding: "1px 5px", fontSize: "0.66rem", flexShrink: 0 }}
                        title="Delete record"
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}

                {/* Upload toggle */}
                <button
                  id="upload-record-btn"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setShowUpload((v) => !v)}
                  style={{ width: "100%", marginTop: 4 }}
                >
                  {showUpload ? "✕ Cancel" : "+ Upload Record"}
                </button>

                {showUpload && (
                  <div className="animate-fade-in" style={{ marginTop: 8 }}>
                    <select
                      id="record-type-select"
                      className="input"
                      value={selectedRecordType}
                      onChange={(e) => setSelectedRecordType(e.target.value)}
                      style={{ marginBottom: 8, fontSize: "0.82rem", padding: "6px 10px" }}
                    >
                      {RECORD_TYPE_OPTIONS.map((t) => (
                        <option key={t} value={t}>
                          {t.replace(/_/g, " ")}
                        </option>
                      ))}
                    </select>

                    <FileDropzone
                      onFiles={handleUpload}
                      uploading={uploading}
                      progress={uploadProgress}
                      label="Drop medical record"
                      sublabel="PDF, DOCX, XLSX, TXT"
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Error toast */}
      {error && (
        <div
          className="animate-fade-in"
          style={{
            margin: "8px",
            padding: "8px 12px",
            background: "rgba(248,113,113,0.1)",
            border: "1px solid rgba(248,113,113,0.3)",
            borderRadius: "var(--radius)",
            fontSize: "0.78rem",
            color: "#f87171",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: "none", color: "#f87171", cursor: "pointer" }}>✕</button>
        </div>
      )}
    </div>
  );
}
