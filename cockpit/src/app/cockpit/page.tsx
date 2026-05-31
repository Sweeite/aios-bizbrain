"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";

interface Meeting {
  time: string;
  title: string;
  attendees: string[];
  brief: string;
}

interface FlaggedItem {
  type: string;
  entity_ref: string;
  label: string;
  since: string;
}

interface HomeSummary {
  pending_count: number;
  meetings: Meeting[];
  flagged: FlaggedItem[];
}

const FLAG_ICONS: Record<string, string> = {
  stalled_deal: "⏸",
  overdue_invoice: "⚠",
};

export default function CockpitHome() {
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/home/summary", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setSummary)
      .catch((e) => setError(`Could not load summary: ${e}`));
  }, []);

  if (error) {
    return (
      <div className="p-8">
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="p-8 text-sm text-muted-foreground">Loading…</div>
    );
  }

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Today</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          What needs your attention right now.
        </p>
      </div>

      {/* Pending Approvals */}
      <Link href="/cockpit/approvals" className="block group">
        <Card className="transition-colors group-hover:ring-primary/40">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Pending Approvals</CardTitle>
              <Badge
                variant={summary.pending_count > 0 ? "default" : "secondary"}
              >
                {summary.pending_count}
              </Badge>
            </div>
            <CardDescription>
              {summary.pending_count > 0
                ? "T3 actions waiting for your review."
                : "Queue is clear — nothing pending."}
            </CardDescription>
          </CardHeader>
        </Card>
      </Link>

      {/* Today's Meetings */}
      <Card>
        <CardHeader>
          <CardTitle>Today&apos;s Meetings</CardTitle>
        </CardHeader>
        <CardContent>
          {summary.meetings.length === 0 ? (
            <p className="text-sm text-muted-foreground">No meetings today.</p>
          ) : (
            <ul className="divide-y divide-border">
              {summary.meetings.map((m, i) => (
                <li key={i} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-start gap-3">
                    <span className="w-12 shrink-0 text-xs font-mono text-muted-foreground pt-0.5">
                      {m.time}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium leading-snug">
                        {m.title}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {m.brief}
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {m.attendees.map((a) => (
                          <Badge key={a} variant="outline" className="text-xs">
                            {a}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Flagged Items */}
      <Card>
        <CardHeader>
          <CardTitle>Flagged Items</CardTitle>
          <CardDescription>
            Agent-surfaced items that need attention.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {summary.flagged.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nothing flagged.</p>
          ) : (
            <ul className="divide-y divide-border">
              {summary.flagged.map((f, i) => (
                <li key={i} className="py-3 first:pt-0 last:pb-0 flex items-start gap-3">
                  <span className="text-base leading-none mt-0.5">
                    {FLAG_ICONS[f.type] ?? "⚑"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm leading-snug">{f.label}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground font-mono">
                      {f.entity_ref}
                    </p>
                  </div>
                  <Badge variant="outline" className="shrink-0 text-xs capitalize">
                    {f.type.replace("_", " ")}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
