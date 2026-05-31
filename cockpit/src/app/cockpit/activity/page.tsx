"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

interface RunSummary {
  run_id: string;
  trigger: string;
  trigger_type: "proactive" | "human-directed";
  primary_agent: string | null;
  outcome: string;
  started_at: string;
}

interface SpanRow {
  span_id: string;
  parent_span_id: string | null;
  actor: string;
  op: string;
  started_at: string;
  ended_at: string | null;
  model_tier: string;
  token_in: number;
  token_out: number;
  status: string;
  eval_label: string | null;
}

interface TraceData {
  run_id: string;
  spans: SpanRow[];
}

const OUTCOME_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  completed: "default",
  parked: "secondary",
  failed: "destructive",
};

const TRIGGER_VARIANT: Record<string, "default" | "outline"> = {
  proactive: "outline",
  "human-directed": "default",
};

function durationMs(span: SpanRow): string {
  if (!span.ended_at) return "—";
  const ms = new Date(span.ended_at).getTime() - new Date(span.started_at).getTime();
  return `${ms}ms`;
}

function SpanTree({ spans }: { spans: SpanRow[] }) {
  if (spans.length === 0) return <p className="text-sm text-muted-foreground">No spans.</p>;

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-border text-left text-muted-foreground">
          <th className="pb-1 pr-3 font-medium">Actor</th>
          <th className="pb-1 pr-3 font-medium">Op</th>
          <th className="pb-1 pr-3 font-medium">Status</th>
          <th className="pb-1 pr-3 font-medium">Tier</th>
          <th className="pb-1 pr-3 font-medium">Tokens in/out</th>
          <th className="pb-1 pr-3 font-medium">Duration</th>
          <th className="pb-1 font-medium">Eval</th>
        </tr>
      </thead>
      <tbody>
        {spans.map((s) => (
          <tr key={s.span_id} className="border-b border-border/50 last:border-0">
            <td className="py-1.5 pr-3 font-mono">{s.actor}</td>
            <td className="py-1.5 pr-3 capitalize">{s.op}</td>
            <td className="py-1.5 pr-3">
              <Badge
                variant={s.status === "ok" ? "default" : "destructive"}
                className="text-[10px]"
              >
                {s.status}
              </Badge>
            </td>
            <td className="py-1.5 pr-3 font-mono">{s.model_tier}</td>
            <td className="py-1.5 pr-3 font-mono">
              {s.token_in}/{s.token_out}
            </td>
            <td className="py-1.5 pr-3 font-mono">{durationMs(s)}</td>
            <td className="py-1.5">
              {s.eval_label ? (
                <Badge variant="outline" className="text-[10px]">
                  {s.eval_label}
                </Badge>
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RunRow({
  run,
  onSelect,
  isOpen,
  trace,
  loadingTrace,
}: {
  run: RunSummary;
  onSelect: (id: string) => void;
  isOpen: boolean;
  trace: TraceData | null;
  loadingTrace: boolean;
}) {
  const ts = new Date(run.started_at).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="border border-border rounded-md overflow-hidden">
      <button
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-muted/40 transition-colors"
        onClick={() => onSelect(run.run_id)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium font-mono truncate">{run.run_id}</span>
            <Badge
              variant={TRIGGER_VARIANT[run.trigger_type] ?? "outline"}
              className="text-xs capitalize shrink-0"
            >
              {run.trigger_type}
            </Badge>
            <Badge
              variant={OUTCOME_VARIANT[run.outcome] ?? "secondary"}
              className="text-xs capitalize shrink-0"
            >
              {run.outcome}
            </Badge>
          </div>
          <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">{run.trigger}</span>
            {run.primary_agent && (
              <>
                <span>·</span>
                <span>{run.primary_agent}</span>
              </>
            )}
            <span>·</span>
            <span>{ts}</span>
          </div>
        </div>
        <span className="text-muted-foreground text-xs shrink-0">{isOpen ? "▲" : "▼"}</span>
      </button>

      {isOpen && (
        <div className="border-t border-border px-4 py-3 bg-muted/20">
          {loadingTrace ? (
            <p className="text-xs text-muted-foreground">Loading trace…</p>
          ) : trace ? (
            <SpanTree spans={trace.spans} />
          ) : (
            <p className="text-xs text-muted-foreground">No trace data.</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function ActivityPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const [traces, setTraces] = useState<Record<string, TraceData>>({});
  const [loadingTrace, setLoadingTrace] = useState(false);

  useEffect(() => {
    fetch("/api/activity", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setRuns)
      .catch((e) => setError(`Could not load activity: ${e}`))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = useCallback(
    async (run_id: string) => {
      if (openRunId === run_id) {
        setOpenRunId(null);
        return;
      }
      setOpenRunId(run_id);
      if (traces[run_id]) return;
      setLoadingTrace(true);
      try {
        const res = await fetch(`/api/runs/${encodeURIComponent(run_id)}/trace`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`${res.status}`);
        const data: TraceData = await res.json();
        setTraces((prev) => ({ ...prev, [run_id]: data }));
      } catch {
        // leave trace null — SpanTree handles missing gracefully
      } finally {
        setLoadingTrace(false);
      }
    },
    [openRunId, traces],
  );

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">Activity Feed</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Recent brain runs — click any row to see the full trace.
        </p>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {error && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && runs.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>No runs yet</CardTitle>
            <CardDescription>
              Trigger a run via the proving script and refresh.
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      )}

      <div className="space-y-2">
        {runs.map((run) => (
          <RunRow
            key={run.run_id}
            run={run}
            onSelect={handleSelect}
            isOpen={openRunId === run.run_id}
            trace={traces[run.run_id] ?? null}
            loadingTrace={loadingTrace && openRunId === run.run_id}
          />
        ))}
      </div>
    </div>
  );
}
