import type { NextRequest } from "next/server";

const apiBase = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.text();
  try {
    const res = await fetch(`${apiBase()}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });

    if (!res.ok || !res.body) {
      return new Response(JSON.stringify({ error: "backend error" }), {
        status: res.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(res.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch {
    return new Response(JSON.stringify({ error: "backend unreachable" }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}
