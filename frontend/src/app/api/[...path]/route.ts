import type { NextRequest } from "next/server";

// The BFF proxy: the browser calls same-origin /api/*, and this Node handler
// forwards to the backend, injecting credentials from SERVER-ONLY env so the
// key never reaches the browser. Never cached.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = (process.env.PROOFLENS_API_URL || "http://localhost:8000").replace(/\/$/, "");
const TENANT_KEY = process.env.PROOFLENS_TENANT_KEY || "";
const ADMIN_TOKEN = process.env.PROOFLENS_ADMIN_TOKEN || "";

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const suffix = path.join("/");
  const search = new URL(req.url).search;
  const url = `${BACKEND}/${suffix}${search}`;

  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (suffix.startsWith("v1/") && TENANT_KEY) headers.set("authorization", `Bearer ${TENANT_KEY}`);
  if (suffix.startsWith("admin/") && ADMIN_TOKEN) headers.set("x-admin-token", ADMIN_TOKEN);

  const method = req.method.toUpperCase();
  const body = method === "GET" || method === "HEAD" ? undefined : await req.arrayBuffer();

  const upstream = await fetch(url, { method, headers, body, redirect: "manual" });
  const respHeaders = new Headers();
  const ct = upstream.headers.get("content-type");
  if (ct) respHeaders.set("content-type", ct);
  return new Response(upstream.body, { status: upstream.status, headers: respHeaders });
}

type Ctx = { params: Promise<{ path: string[] }> };
const handler = async (req: NextRequest, ctx: Ctx) => proxy(req, (await ctx.params).path);

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
