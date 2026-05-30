export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-24">
      <div className="text-center">
        <h1 className="text-3xl font-bold tracking-tight">AIOS BizBrain</h1>
        <p className="mt-2 text-muted-foreground">Cockpit — Slice 1 scaffold</p>
      </div>
      <div className="flex gap-3">
        <a
          href="/cockpit"
          className="inline-flex h-8 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80"
        >
          Open Cockpit
        </a>
        <a
          href="/api/health"
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-8 items-center justify-center rounded-lg border border-border bg-background px-4 text-sm font-medium transition-colors hover:bg-muted"
        >
          API Health
        </a>
      </div>
    </main>
  );
}
