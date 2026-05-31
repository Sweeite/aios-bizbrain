import { NextResponse } from "next/server";

const apiBase = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function GET() {
  try {
    const res = await fetch(`${apiBase()}/approvals`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 503 });
  }
}
