import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const apiBase = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ run_id: string }> },
) {
  const { run_id } = await params;
  try {
    const res = await fetch(`${apiBase()}/runs/${encodeURIComponent(run_id)}/trace`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json({ error: "not found" }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 503 });
  }
}
