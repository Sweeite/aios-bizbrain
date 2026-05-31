"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface ClientSummary {
  id: string;
  name: string;
  deal_stage: string | null;
  deal_name: string | null;
}

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/clients", { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then(setClients)
      .catch((e) => setError(`Could not load clients: ${e}`))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">Clients</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          All clients in scope — click to view full profile.
        </p>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {error && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && clients.length === 0 && (
        <Card>
          <CardHeader>
            <CardTitle>No clients found</CardTitle>
            <CardDescription>No clients are in scope.</CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      )}

      <div className="space-y-3">
        {clients.map((c) => (
          <Link
            key={c.id}
            href={`/cockpit/clients/${encodeURIComponent(c.id)}`}
            className="block rounded-lg border border-border p-4 hover:bg-muted/40 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{c.name}</p>
                <p className="text-xs text-muted-foreground font-mono mt-0.5">
                  {c.id}
                </p>
              </div>
              {c.deal_stage ? (
                <Badge variant="secondary">{c.deal_stage}</Badge>
              ) : (
                <Badge variant="outline">No active deal</Badge>
              )}
            </div>
            {c.deal_name && (
              <p className="text-sm text-muted-foreground mt-1">{c.deal_name}</p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
