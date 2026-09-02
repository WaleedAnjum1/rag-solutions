"use client";

import { useEffect, useRef, useState } from "react";
import type { Source } from "@/lib/types";
import { SourceCitations } from "./SourceCitations";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
  error?: string;
}

interface Props {
  onSend: (question: string) => Promise<void>;
  streamingAnswer: string;
  streamingSources: Source[];
  isStreaming: boolean;
  streamError: string | null;
  onReset: () => void;
  suggestions?: string[];
  emptyTitle?: string;
  emptySubtitle?: string;
}

let idCounter = 0;
const uid = () => `msg-${++idCounter}-${Date.now()}`;

export function ChatPanel({
  onSend,
  streamingAnswer,
  streamingSources,
  isStreaming,
  streamError,
  onReset,
  suggestions = [],
  emptyTitle = "Ask anything",
  emptySubtitle = "Upload a document to get started",
}: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Track which assistant message id is currently streaming
  const streamingMsgId = useRef<string | null>(null);

  // Update the streaming message in place as tokens arrive
  useEffect(() => {
    if (!streamingMsgId.current) return;
    const id = streamingMsgId.current;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === id
          ? { ...m, content: streamingAnswer, isStreaming, sources: isStreaming ? [] : streamingSources }
          : m
      )
    );
    if (!isStreaming) streamingMsgId.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamingAnswer, isStreaming]);

  // Scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const q = input.trim();
    if (!q || isStreaming) return;

    setInput("");

    const userMsg: Message = { id: uid(), role: "user", content: q };
    const assistantId = uid();
    streamingMsgId.current = assistantId;

    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    onReset(); // clear previous stream state before starting new one
    await onSend(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([]);
    onReset();
    streamingMsgId.current = null;
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        background: "var(--bg-base)",
        position: "relative",
      }}
    >
      {/* Messages area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 24px 8px",
          display: "flex",
          flexDirection: "column",
          gap: 20,
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              padding: "60px 20px",
              textAlign: "center",
            }}
          >
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: "var(--radius-lg)",
                background: "var(--accent-dim)",
                border: "1px solid var(--accent)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 28,
                boxShadow: "var(--accent-glow)",
              }}
            >
              💬
            </div>
            <div>
              <h3 style={{ color: "var(--text-primary)", marginBottom: 4 }}>{emptyTitle}</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>{emptySubtitle}</p>
            </div>

            {suggestions.length > 0 && (
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 8,
                  justifyContent: "center",
                  marginTop: 8,
                }}
              >
                {suggestions.map((s) => (
                  <button
                    key={s}
                    className="btn btn-ghost btn-sm"
                    onClick={() => {
                      setInput(s);
                      inputRef.current?.focus();
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className="animate-slide-up"
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: msg.role === "user" ? "flex-end" : "flex-start",
              gap: 6,
            }}
          >
            {/* Role label */}
            <span
              style={{
                fontSize: "0.7rem",
                fontWeight: 600,
                color: "var(--text-muted)",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                padding: "0 4px",
              }}
            >
              {msg.role === "user" ? "You" : "RAG Assistant"}
            </span>

            {/* Bubble */}
            <div
              style={{
                maxWidth: "82%",
                background:
                  msg.role === "user" ? "var(--accent-dim)" : "var(--bg-surface)",
                border: `1px solid ${
                  msg.role === "user" ? "var(--accent)" : "var(--border)"
                }`,
                borderRadius:
                  msg.role === "user"
                    ? "var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg)"
                    : "var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm)",
                padding: "12px 16px",
                fontSize: "0.9rem",
                lineHeight: 1.65,
                color: "var(--text-primary)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
              className={msg.isStreaming && msg.content ? "cursor-blink" : ""}
            >
              {msg.isStreaming && !msg.content ? (
                <span style={{ color: "var(--text-muted)" }}>
                  <ThreeDots />
                </span>
              ) : (
                msg.content
              )}
            </div>

            {/* Error state */}
            {msg.role === "assistant" && streamError && !isStreaming && msg.id === messages[messages.length - 1]?.id && (
              <p style={{ fontSize: "0.8rem", color: "#f87171", padding: "0 4px" }}>
                ⚠ {streamError}
              </p>
            )}

            {/* Sources */}
            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <div style={{ maxWidth: "82%", width: "100%" }}>
                <SourceCitations sources={msg.sources} />
              </div>
            )}
          </div>
        ))}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div
        style={{
          padding: "12px 24px 20px",
          borderTop: "1px solid var(--border)",
          background: "var(--bg-base)",
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
          <textarea
            ref={inputRef}
            id="chat-input"
            className="input"
            rows={1}
            placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming}
            style={{
              resize: "none",
              minHeight: 44,
              maxHeight: 140,
              flex: 1,
              lineHeight: 1.5,
            }}
          />

          <button
            id="chat-send-btn"
            className="btn btn-primary"
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
            style={{ flexShrink: 0, height: 44 }}
          >
            {isStreaming ? "…" : "Send"}
          </button>
        </div>

        {messages.length > 0 && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={clearChat}
            style={{ alignSelf: "flex-start" }}
          >
            Clear chat
          </button>
        )}
      </div>
    </div>
  );
}

function ThreeDots() {
  return (
    <span style={{ display: "inline-flex", gap: 4, alignItems: "center", padding: "2px 0" }}>
      {[0, 0.2, 0.4].map((delay, i) => (
        <span
          key={i}
          style={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            background: "var(--accent)",
            display: "inline-block",
            animation: `pulse-dot 1.2s ease-in-out ${delay}s infinite`,
          }}
        />
      ))}
    </span>
  );
}
