"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface EpisodicRecord {
  store: string;
  payload: Record<string, unknown>;
  confidence: string;
  as_of: string;
  source: string;
}

interface EntityFact extends EpisodicRecord {}

interface BrainUnderstanding {
  entity_facts: EntityFact[];
  episodic_history: EpisodicRecord[];
}

interface Deal {
  deal_name: string | null;
  stage: string | null;
  days_in_stage: number | null;
}

interface Budget {
  engagement: string | null;
  budget_usd: number | null;
  spent_usd: number | null;
  event_type: string;
}

interface Task {
  task_name: string | null;
  event_type: string;
  project: string | null;
}

interface Invoice {
  invoice_number: string | null;
  amount_usd: number | null;
  event_type: string;
}

interface LiveStatus {
  deal: Deal | null;
  budget: Budget | null;
  open_tasks: Task[];
  invoices: Invoice[];
}

interface ClientProfile {
  id: string;
  name: string;
  brain_understanding: BrainUnderstanding;
  live_status: LiveStatus;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
      {children}
    </p>
  );
}

function EpisodicRow({ record }: { record: EpisodicRecord }) {
  const asOf = record.as_of
    ? new Date(record.as_of).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "—";

  const eventType = (record.payload["event_type"] as string) ?? record.source;

  return (
    <div className="border border-border rounded-md px-3 py-2 text-sm">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="font-mono text-xs text-muted-foreground">{eventType}</span>
        <Badge variant="outline" className="text-[10px]">
          {record.confidence}
        </Badge>
        <span className="text-xs text-muted-foreground ml-auto">{asOf}</span>
      </div>
      <div className="mt-1 text-xs text-muted-foreground space-y-0.5">
        {Object.entries(record.payload)
          .filter(([k]) => k !== "source_event_id" && k !== "event_type")
          .map(([k, v]) => (
            <div key={k} className="flex gap-1">
              <span className="font-medium">{k}:</span>
              <span>{String(v)}</span>
            </div>
          ))}
      </div>
    </div>
  );
}

export default function ClientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/clients/${encodeURIComponent(id)}`, { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setProfile)
      .catch((e) => setError(`Could not load profile: ${e}`))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6 flex items-center gap-3">
        <Link
          href="/cockpit/clients"
          className="text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          ← Clients
        </Link>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {error && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {profile && (
        <div className="space-y-6">
          {/* Header */}
          <div>
            <h2 className="text-2xl font-semibold">{profile.name}</h2>
            <p className="text-xs font-mono text-muted-foreground mt-0.5">
              {profile.id}
            </p>
          </div>

          {/* Live Status — source-system facts */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Live Status</CardTitle>
              <CardDescription>
                Current facts from source systems — deal stage, budget, tasks,
                invoices.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.live_status.deal && (
                <div>
                  <SectionLabel>Active Deal</SectionLabel>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">
                      {profile.live_status.deal.deal_name}
                    </span>
                    <Badge variant="secondary">
                      {profile.live_status.deal.stage}
                    </Badge>
                    {profile.live_status.deal.days_in_stage != null && (
                      <span className="text-xs text-muted-foreground">
                        {profile.live_status.deal.days_in_stage}d in stage
                      </span>
                    )}
                  </div>
                </div>
              )}

              {profile.live_status.budget && (
                <div>
                  <SectionLabel>Engagement Budget</SectionLabel>
                  <p className="text-sm">
                    {profile.live_status.budget.engagement}
                  </p>
                  <div className="mt-1 flex gap-4 text-xs text-muted-foreground">
                    <span>
                      Budget: ${profile.live_status.budget.budget_usd?.toLocaleString()}
                    </span>
                    <span>
                      Spent: ${profile.live_status.budget.spent_usd?.toLocaleString()}
                    </span>
                    {profile.live_status.budget.budget_usd &&
                      profile.live_status.budget.spent_usd && (
                        <span>
                          {Math.round(
                            (profile.live_status.budget.spent_usd /
                              profile.live_status.budget.budget_usd) *
                              100,
                          )}
                          % used
                        </span>
                      )}
                  </div>
                </div>
              )}

              {profile.live_status.open_tasks.length > 0 && (
                <div>
                  <SectionLabel>Asana Tasks</SectionLabel>
                  <div className="space-y-1">
                    {profile.live_status.open_tasks.map((t, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <Badge variant="outline" className="text-[10px]">
                          {t.event_type.replace("_", " ")}
                        </Badge>
                        <span>{t.task_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {profile.live_status.invoices.length > 0 && (
                <div>
                  <SectionLabel>Invoices</SectionLabel>
                  <div className="space-y-1">
                    {profile.live_status.invoices.map((inv, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm">
                        <span className="font-mono">{inv.invoice_number}</span>
                        <span>${inv.amount_usd?.toLocaleString()}</span>
                        <Badge variant="outline" className="text-[10px]">
                          {inv.event_type}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {!profile.live_status.deal &&
                !profile.live_status.budget &&
                profile.live_status.open_tasks.length === 0 &&
                profile.live_status.invoices.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No live data for this client.
                  </p>
                )}
            </CardContent>
          </Card>

          {/* Brain Understanding — memory-derived */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Brain Understanding</CardTitle>
              <CardDescription>
                What the brain has learned from experience — episodic history
                and promoted entity facts.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {profile.brain_understanding.entity_facts.length > 0 && (
                <div>
                  <SectionLabel>Entity Facts (promoted patterns)</SectionLabel>
                  <div className="space-y-2">
                    {profile.brain_understanding.entity_facts.map((r, i) => (
                      <EpisodicRow key={i} record={r} />
                    ))}
                  </div>
                </div>
              )}

              {profile.brain_understanding.episodic_history.length > 0 ? (
                <div>
                  <SectionLabel>Episodic History</SectionLabel>
                  <div className="space-y-2">
                    {profile.brain_understanding.episodic_history.map(
                      (r, i) => (
                        <EpisodicRow key={i} record={r} />
                      ),
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No episodic memory for this client yet.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
