"use client";

import { useCallback, useRef, useState } from "react";
import type { Source, SSEToken } from "@/lib/types";

export interface StreamState {
  answer: string;
  sources: Source[];
  isStreaming: boolean;
  error: string | null;
}

/**
 * useStreamQuery — fires a POST to a streaming SSE endpoint, appends tokens
 * as they arrive, and collects sources from the final done event.
 *
 * Usage:
 *   const { stream, state, reset } = useStreamQuery();
 *   await stream(() => medicalApi.streamQuery(question, patientId));
 */
export function useStreamQuery() {
  const [state, setState] = useState<StreamState>({
    answer: "",
    sources: [],
    isStreaming: false,
    error: null,
  });

  // Abort controller so callers can cancel mid-stream
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setState({ answer: "", sources: [], isStreaming: false, error: null });
  }, []);

  const stream = useCallback(
    async (fetchFn: () => Promise<Response>) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      setState({ answer: "", sources: [], isStreaming: true, error: null });

      try {
        const res = await fetchFn();

        if (!res.ok) {
          const text = await res.text().catch(() => res.statusText);
          throw new Error(text || `HTTP ${res.status}`);
        }

        if (!res.body) throw new Error("No response body for streaming");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          if (abortRef.current.signal.aborted) break;

          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE lines arrive as "data: {...}\n\n" — process complete events
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? ""; // keep incomplete last line in buffer

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;

            try {
              const payload: SSEToken = JSON.parse(trimmed.slice(5).trim());

              if (payload.error) {
                setState((prev) => ({
                  ...prev,
                  isStreaming: false,
                  error: payload.error ?? "Stream error",
                }));
                return;
              }

              if (payload.done) {
                setState((prev) => ({
                  ...prev,
                  isStreaming: false,
                  sources: payload.sources ?? [],
                }));
              } else if (payload.token) {
                setState((prev) => ({
                  ...prev,
                  answer: prev.answer + payload.token,
                }));
              }
            } catch {
              // Malformed JSON in SSE line — skip silently
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: (err as Error).message,
        }));
      }
    },
    []
  );

  return { stream, state, reset };
}
