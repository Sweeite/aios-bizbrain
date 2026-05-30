import { NextResponse } from "next/server";

export async function GET() {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiBase}/health`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json({ cockpit: "ok", api: data });
  } catch {
    return NextResponse.json(
      { cockpit: "ok", api: "unreachable" },
      { status: 503 }
    );
  }
}
