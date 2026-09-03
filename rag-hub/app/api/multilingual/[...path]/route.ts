import { type NextRequest } from "next/server";

const UPSTREAM = process.env.MULTILINGUAL_API_URL ?? "http://localhost:8300";

/**
 * Catch-all proxy → multilingual-support-bot at :8300
 *
 * Forwards all methods (GET, POST, DELETE) including SSE streams.
 */
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, await params);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, await params);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxy(req, await params);
}

async function proxy(
  req: NextRequest,
  params: { path: string[] }
) {
  const path = params.path?.join("/") ?? "";
  const search = req.nextUrl.search ?? "";
  const url = `${UPSTREAM}/${path}${search}`;

  // Forward body for POST/PUT/PATCH; skip for GET/DELETE
  const hasBody = req.method !== "GET" && req.method !== "DELETE" && req.method !== "HEAD";
  const bodyBuffer = hasBody ? await req.arrayBuffer() : undefined;

  // Forward relevant headers — drop host to avoid SNI mismatch
  const forwardHeaders = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) forwardHeaders.set("content-type", contentType);
  forwardHeaders.set("accept", req.headers.get("accept") ?? "*/*");

  try {
    const upstreamRes = await fetch(url, {
      method: req.method,
      headers: forwardHeaders,
      body: bodyBuffer,
    });

    // Stream the response back — preserves SSE text/event-stream
    return new Response(upstreamRes.body, {
      status: upstreamRes.status,
      headers: {
        "content-type": upstreamRes.headers.get("content-type") ?? "application/json",
        "cache-control": "no-cache",
        "x-accel-buffering": "no",
      },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ detail: "Service unavailable", error: String(err) }),
      { status: 503, headers: { "content-type": "application/json" } }
    );
  }
}
