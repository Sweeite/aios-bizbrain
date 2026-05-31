"use client";

import { useCallback, useEffect, useState } from "react";
import { ApprovalCard, ApprovalRequest } from "@/components/approval-card";

export default function ApprovalsPage() {
  const [requests, setRequests] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchQueue = useCallback(async () => {
    try {
      const res = await fetch("/api/approvals", { cache: "no-store" });
      if (!res.ok) throw new Error(`${res.status}`);
      setRequests(await res.json());
      setError(null);
    } catch (e) {
      setError(`Could not reach the backend: ${e}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
  }, [fetchQueue]);

  function handleResolved(key: string) {
    setRequests((prev) => prev.filter((r) => r.idempotency_key !== key));
  }

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold">Approval Queue</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          T3 actions awaiting your review before execution.
        </p>
      </div>

      {loading && (
        <p className="text-sm text-muted-foreground">Loading…</p>
      )}

      {error && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && !error && requests.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No pending approvals. The queue is empty.
        </p>
      )}

      <div className="space-y-4">
        {requests.map((req) => (
          <ApprovalCard
            key={req.idempotency_key}
            request={req}
            onResolved={handleResolved}
          />
        ))}
      </div>
    </div>
  );
}
