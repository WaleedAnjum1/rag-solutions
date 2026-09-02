"use client";

import { useCallback, useRef, useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  uploading?: boolean;
  progress?: number; // 0–100
  label?: string;
  sublabel?: string;
}

export function FileDropzone({
  onFiles,
  accept = ".pdf,.docx,.txt,.md,.xlsx,.xls,.csv",
  multiple = false,
  uploading = false,
  progress = 0,
  label = "Drop files here",
  sublabel = "PDF, DOCX, XLSX, TXT, MD up to 50 MB",
}: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length) onFiles(files);
    },
    [onFiles]
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length) onFiles(files);
      e.target.value = "";
    },
    [onFiles]
  );

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="File upload area"
      onDragEnter={() => setIsDragging(true)}
      onDragLeave={() => setIsDragging(false)}
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => !uploading && inputRef.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && !uploading && inputRef.current?.click()}
      style={{
        border: `2px dashed ${isDragging ? "var(--accent)" : "var(--border-strong)"}`,
        borderRadius: "var(--radius-lg)",
        background: isDragging ? "var(--accent-dim)" : "var(--bg-elevated)",
        padding: "32px 24px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        cursor: uploading ? "default" : "pointer",
        transition: "all 150ms ease",
        boxShadow: isDragging ? "var(--accent-glow)" : "none",
        outline: "none",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={handleChange}
      />

      {/* Icon */}
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: "var(--radius)",
          background: "var(--accent-dim)",
          border: "1px solid var(--accent)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 22,
          transition: "transform 150ms ease",
          transform: isDragging ? "scale(1.1)" : "scale(1)",
        }}
      >
        {uploading ? "⏳" : "📄"}
      </div>

      <div style={{ textAlign: "center" }}>
        <p style={{ color: "var(--text-primary)", fontWeight: 600, fontSize: "0.9rem" }}>
          {uploading ? "Uploading…" : label}
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: "0.78rem", marginTop: 2 }}>
          {sublabel}
        </p>
      </div>

      {/* Progress bar */}
      {uploading && (
        <div
          style={{
            width: "100%",
            height: 4,
            background: "var(--border)",
            borderRadius: 99,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${progress}%`,
              background: "var(--accent)",
              borderRadius: 99,
              transition: "width 300ms ease",
            }}
          />
        </div>
      )}
    </div>
  );
}
