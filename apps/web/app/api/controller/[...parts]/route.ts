import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { authorizedOperator } from "@/lib/supabase";
import { allowedRequest, controllerOrigin } from "@/lib/controller";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
const responseHeaders = { "Cache-Control": "private, no-store, max-age=0", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff" };
const taskLaunch = z.object({
  task: z.string().min(1).max(96),
  config: z.record(z.string(), z.unknown()),
  request_id: z.uuid(),
  confirmed: z.literal(true)
}).strict();
const buildingTargets = z.object({ upgrades: z.array(z.object({
  position: z.number().int().min(0).max(80),
  target_level: z.number().int().min(1).max(150)
}).strict()).min(1).max(12) }).strict();

type RouteContext = { params: Promise<{ parts: string[] }> };
async function proxy(request: NextRequest, context: RouteContext) {
  const operator = await authorizedOperator();
  if (operator.state !== "authorized") return NextResponse.json({ error: "Access denied" }, { status: 401, headers: responseHeaders });
  const { parts } = await context.params;
  const url = new URL(request.url);
  if (!allowedRequest(request.method, parts, url.searchParams)) return NextResponse.json({ error: "Operation unavailable in web control center" }, { status: 404, headers: responseHeaders });
  if (request.method !== "GET" && operator.role === "viewer") return NextResponse.json({ error: "Read-only administrator" }, { status: 403, headers: responseHeaders });
  if (request.method !== "GET" && request.headers.get("origin") !== url.origin)
    return NextResponse.json({ error: "Invalid request origin" }, { status: 403, headers: responseHeaders });
  const origin = controllerOrigin();
  const token = process.env.DAEDALUS_API_TOKEN;
  if (!origin || !token || token.length < 32) return NextResponse.json({ error: "Backend connection is not provisioned" }, { status: 503, headers: responseHeaders });
  let body: string | undefined;
  if (request.method !== "GET") {
    if (Number(request.headers.get("content-length") ?? 0) > 16000) return NextResponse.json({ error: "Request too large" }, { status: 413, headers: responseHeaders });
    const raw = await request.text();
    if (raw.length > 16000) return NextResponse.json({ error: "Request too large" }, { status: 413, headers: responseHeaders });
    let value: unknown;
    try { value = JSON.parse(raw); } catch { return NextResponse.json({ error: "Invalid request" }, { status: 400, headers: responseHeaders }); }
    if (request.method === "POST" && parts.length === 3 && parts[2] === "tasks" && !taskLaunch.safeParse(value).success)
      return NextResponse.json({ error: "Invalid task confirmation" }, { status: 422, headers: responseHeaders });
    if (parts.at(-1) === "construction-preview" && !buildingTargets.safeParse(value).success)
      return NextResponse.json({ error: "Invalid construction targets" }, { status: 422, headers: responseHeaders });
    if (parts.at(-1) === "acknowledge" && JSON.stringify(value) !== '{"confirmed":true}')
      return NextResponse.json({ error: "Explicit confirmation required" }, { status: 422, headers: responseHeaders });
    body = JSON.stringify(value);
  }
  const query = parts.at(-1) === "preflight" ? "?task=" + encodeURIComponent(url.searchParams.get("task") ?? "")
    : parts.at(-1) === "market-quotes" ? "?resource_type=" + encodeURIComponent(url.searchParams.get("resource_type") ?? "") + "&side=" + encodeURIComponent(url.searchParams.get("side") ?? "")
    : parts.at(-1) === "trainable-units" && url.searchParams.has("train_troops") ? "?train_troops=" + encodeURIComponent(url.searchParams.get("train_troops") ?? "") : "";
  try {
    const upstream = await fetch(origin + "/api/v1/" + parts.map(encodeURIComponent).join("/") + query, {
      method: request.method, body,
      headers: { "Authorization": "Bearer " + token, ...(body ? { "Content-Type": "application/json" } : {}) },
      redirect: "error", cache: "no-store", signal: AbortSignal.timeout(request.method === "GET" ? 12000 : 25000)
    });
    const text = await upstream.text();
    if (text.length > 2_000_000) return NextResponse.json({ error: "Response exceeds limit" }, { status: 502, headers: responseHeaders });
    let result: unknown;
    try { result = JSON.parse(text); } catch { result = { error: "Invalid backend response" }; }
    if (!upstream.ok) return NextResponse.json({ error: "Backend request could not complete", status: upstream.status }, { status: upstream.status >= 400 && upstream.status <= 599 ? upstream.status : 502, headers: responseHeaders });
    return NextResponse.json(result, { status: upstream.status, headers: responseHeaders });
  } catch {
    return NextResponse.json({ error: request.method === "GET" ? "Backend temporarily unreachable" : "Request outcome uncertain — check Activity before retrying" }, { status: 503, headers: responseHeaders });
  }
}
export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
