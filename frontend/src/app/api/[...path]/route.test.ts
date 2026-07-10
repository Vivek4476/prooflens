import { afterEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "./route";

function req(url: string, init?: RequestInit) {
  // NextRequest is a superset of Request for our purposes here.
  return new Request(url, init) as unknown as import("next/server").NextRequest;
}

afterEach(() => vi.restoreAllMocks());

describe("BFF proxy", () => {
  it("injects the bearer key on v1/* and forwards status + query", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const res = await GET(req("http://localhost:3000/api/v1/results?limit=5"), {
      params: Promise.resolve({ path: ["v1", "results"] }),
    });
    expect(res.status).toBe(200);
    const [calledUrl, calledInit] = fetchMock.mock.calls[0];
    expect(String(calledUrl)).toContain("/v1/results?limit=5");
    expect((calledInit!.headers as Headers).get("authorization")).toMatch(/^Bearer /);
  });

  it("injects the admin token on admin/* and not the bearer key", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } }),
    );
    await GET(req("http://localhost:3000/api/admin/tenants"), {
      params: Promise.resolve({ path: ["admin", "tenants"] }),
    });
    const init = fetchMock.mock.calls[0][1]!;
    const headers = init.headers as Headers;
    expect(headers.get("x-admin-token")).toBeTruthy();
    expect(headers.get("authorization")).toBeNull();
  });

  it("forwards a POST body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 202, headers: { "content-type": "application/json" } }),
    );
    const res = await POST(
      req("http://localhost:3000/api/v1/bulk-score", {
        method: "POST",
        body: JSON.stringify({ rows: [] }),
        headers: { "content-type": "application/json" },
      }),
      { params: Promise.resolve({ path: ["v1", "bulk-score"] }) },
    );
    expect(res.status).toBe(202);
    expect(fetchMock.mock.calls[0][1]!.method).toBe("POST");
  });
});
