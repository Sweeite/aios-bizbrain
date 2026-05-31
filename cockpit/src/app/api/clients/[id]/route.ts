import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const apiBase = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const scope = req.nextUrl.searchParams.get("scope");
  const url = scope
    ? `${apiBase()}/clients/${encodeURIComponent(id)}?scope=${encodeURIComponent(scope)}`
    : `${apiBase()}/clients/${encodeURIComponent(id)}`;
  try {
    const res = await fetch(url, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 503 });
  }
}
