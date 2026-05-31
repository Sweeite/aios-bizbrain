import { NextResponse } from "next/server";

const apiBase = () =>
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const scope = searchParams.get("scope");
  const url = new URL(`${apiBase()}/home/summary`);
  if (scope) url.searchParams.set("scope", scope);

  try {
    const res = await fetch(url.toString(), { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "backend unreachable" }, { status: 503 });
  }
}
