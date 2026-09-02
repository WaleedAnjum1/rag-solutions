import { type NextRequest } from "next/server";

const UPSTREAM = process.env.DOCS_API_URL ?? "http://localhost:8100";

/**
 * Catch-all proxy → doc-qa-service at :8100
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

  const hasBody = req.method !== "GET" && req.method !== "DELETE" && req.method !== "HEAD";

  const forwardHeaders = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) forwardHeaders.set("content-type", contentType);
  forwardHeaders.set("accept", req.headers.get("accept") ?? "*/*");

  try {
    const upstreamRes = await fetch(url, {
      method: req.method,
      headers: forwardHeaders,
      body: hasBody ? req.body : undefined,
      // @ts-expect-error — Node.js fetch duplex option
      duplex: "half",
    });

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
