"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ConnectorHealth {
  source_system: string;
  status: "healthy" | "degraded" | "broken";
  last_sync_at: string | null;
  error_message: string | null;
}

const DISPLAY_NAMES: Record<string, string> = {
  hubspot: "HubSpot",
  gmail: "Gmail",
  calendar: "Google Calendar",
  asana: "Asana",
  slack: "Slack",
  quickbooks: "QuickBooks",
  harvest: "Harvest",
  zoom: "Zoom",
};

function relativeTime(iso: string | null): string {
  if (!iso) return "Never";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

const STATUS_BADGE: Record<
  ConnectorHealth["status"],
  { variant: "default" | "secondary" | "destructive" | "outline"; label: string }
> = {
  healthy: { variant: "default", label: "Healthy" },
  degraded: { variant: "secondary", label: "Degraded" },
  broken: { variant: "destructive", label: "Broken" },
};

function ConnectorRow({
  record,
  onReconnect,
  reconnecting,
}: {
  record: ConnectorHealth;
  onReconnect: (system: string) => void;
  reconnecting: boolean;
}) {
  const badge = STATUS_BADGE[record.status];
  const name = DISPLAY_NAMES[record.source_system] ?? record.source_system;

  return (
    <div className="rounded-lg border border-border p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium">{name}</p>
            <Badge variant={badge.variant} className="text-xs">
              {badge.label}
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 font-mono">
            Last sync: {relativeTime(record.last_sync_at)}
          </p>
        </div>
        {record.status === "broken" && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onReconnect(record.source_system)}
            disabled={reconnecting}
          >
            {reconnecting ? "Reconnecting…" : "Reconnect"}
          </Button>
        )}
      </div>
      {record.status === "broken" && record.error_message && (
        <div className="mt-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive font-mono">
          {record.error_message}
        </div>
      )}
    </div>
  );
}

export default function IntegrationsPage() {
  const [records, setRecords] = useState<ConnectorHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reconnecting, setReconnecting] = useState<string | null>(null);

  const loadHealth = useCallback(() => {
    setLoading(true);
    fetch("/api/integrations/health", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setRecords)
      .catch((e) => setError(`Could not load integrations: ${e}`))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  const handleReconnect = useCallback(
    async (system: string) => {
      setReconnecting(system);
      try {
        const res = await fetch(
          `/api/integrations/${encodeURIComponent(system)}/reconnect`,
          { method: "POST" },
        );
        if (!res.ok) throw new Error(`${res.status}`);
        loadHealth();
      } catch {
        // refresh anyway so stale state doesn't linger
        loadHealth();
      } finally {
        setReconnecting(null);
      }
    },
    [loadHealth],
  );

  const brokenCount = records.filter((r) => r.status === "broken").length;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">Integrations</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Health status of every connected system. First place to check when the
          brain goes silent on a source.
        </p>
      </div>

      {brokenCount > 0 && (
        <div className="mb-4 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {brokenCount} connector{brokenCount > 1 ? "s" : ""} need
          {brokenCount === 1 ? "s" : ""} attention.
        </div>
      )}

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {error && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && records.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>No connectors found</CardTitle>
            <CardDescription>No integration health data available.</CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      )}

      <div className="space-y-3">
        {records.map((r) => (
          <ConnectorRow
            key={r.source_system}
            record={r}
            onReconnect={handleReconnect}
            reconnecting={reconnecting === r.source_system}
          />
        ))}
      </div>
    </div>
  );
}
