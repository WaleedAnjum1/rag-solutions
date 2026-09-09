import { type NextRequest } from "next/server";

const UPSTREAM = process.env.LEGAL_API_URL ?? "http://localhost:8500";
const PUBLIC_TENANT = process.env.LEGAL_PUBLIC_TENANT ?? "firm_public";
const ALLOWED_ORIGINS = (process.env.LEGAL_ALLOWED_ORIGINS ?? "").split(",").filter(Boolean);

// Simple in-memory rate limiter (token bucket)
// ~20 req / 5 min
const rateLimitCache = new Map<string, { tokens: number; lastRefill: number }>();
const REFILL_RATE = 20 / (5 * 60 * 1000); // tokens per ms
const MAX_TOKENS = 20;

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  let state = rateLimitCache.get(ip);
  if (!state) {
    state = { tokens: MAX_TOKENS, lastRefill: now };
  } else {
    const elapsed = now - state.lastRefill;
    state.tokens = Math.min(MAX_TOKENS, state.tokens + elapsed * REFILL_RATE);
    state.lastRefill = now;
  }
  
  if (state.tokens < 1) {
    rateLimitCache.set(ip, state);
    return false;
  }
  
  state.tokens -= 1;
  rateLimitCache.set(ip, state);
  return true;
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const p = await params;
  const path = p.path?.join("/") ?? "";
  
  if (path !== "taxonomy" && path !== "health") {
    return new Response("Not Found", { status: 404 });
  }
  return proxy(req, p.path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const p = await params;
  const path = p.path?.join("/") ?? "";
  
  if (path !== "query/stream") {
    return new Response("Not Found", { status: 404 });
  }

  // Rate limit
  const ip = req.headers.get("x-forwarded-for") ?? "unknown";
  if (!checkRateLimit(ip)) {
    return new Response("Too Many Requests", { status: 429 });
  }

  // Origin check
  if (ALLOWED_ORIGINS.length > 0) {
    const origin = req.headers.get("origin") ?? req.headers.get("referer") ?? "";
    const isAllowed = ALLOWED_ORIGINS.some(allowed => origin.startsWith(allowed));
    if (!isAllowed) {
      return new Response("Forbidden", { status: 403 });
    }
  }

  // Body clamp & Server-forced tenant
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return new Response("Invalid JSON", { status: 400 });
  }
  
  if (typeof body.question === "string" && body.question.length > 1500) {
    return new Response("Question too long", { status: 400 });
  }
  
  body.tenant_id = PUBLIC_TENANT;
  body.top_k = 8; // force default
  
  const modifiedReq = new Request(req.url, {
    method: "POST",
    headers: req.headers,
    body: JSON.stringify(body),
  });
  
  return proxy(modifiedReq, p.path);
}

async function proxy(req: Request, pathArray: string[]) {
  const path = pathArray?.join("/") ?? "";
  const url = `${UPSTREAM}/${path}`;

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const bodyBuffer = hasBody ? await req.arrayBuffer() : undefined;

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
