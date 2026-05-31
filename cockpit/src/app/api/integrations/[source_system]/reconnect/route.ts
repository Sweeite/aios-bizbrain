import { NextRequest, NextResponse } from "next/server";

const apiBase = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ source_system: string }> },
) {
  const { source_system } = await params;
  try {
    const res = await fetch(
      `${apiBase()}/integrations/${encodeURIComponent(source_system)}/reconnect`,
      { method: "POST", cache: "no-store" },
    );
    if (res.status === 404) {
      return NextResponse.json({ error: "not found" }, { status: 404 });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 503 });
  }
}
