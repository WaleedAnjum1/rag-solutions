export const legalPublicApi = {
  async streamQuery(question: string, practiceArea?: string): Promise<Response> {
    const payload: Record<string, unknown> = {
      question,
      stream: true,
      top_k: 8,
    };
    
    if (practiceArea) {
      payload.practice_area_filter = practiceArea;
    }

    const res = await fetch("/api/legal-public/query/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      throw new Error("Failed to query Legal Public API");
    }

    return res;
  },
};
