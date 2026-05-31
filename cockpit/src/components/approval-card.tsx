"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Message, MessageAvatar, MessageContent } from "@/components/ui/message";

export interface ApprovalRequest {
  idempotency_key: string;
  action: string;
  preview: string;
  requesting_agent: string;
  principal: string;
  rationale: string;
  scope: {
    level: string;
    entity_ref?: string;
    team_ref?: string;
    user_ref?: string;
  };
}

interface ApprovalCardProps {
  request: ApprovalRequest;
  onResolved: (key: string) => void;
}

type Mode = "idle" | "editing" | "rejecting";

export function ApprovalCard({ request, onResolved }: ApprovalCardProps) {
  const [mode, setMode] = useState<Mode>("idle");
  const [editedBody, setEditedBody] = useState(request.preview);
  const [rejectReason, setRejectReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleApprove(overrideBody?: string) {
    setBusy(true);
    const body = overrideBody !== undefined ? { body: overrideBody } : {};
    await fetch(`/api/approvals/${request.idempotency_key}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setBusy(false);
    onResolved(request.idempotency_key);
  }

  async function handleReject() {
    if (!rejectReason.trim()) return;
    setBusy(true);
    await fetch(`/api/approvals/${request.idempotency_key}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: rejectReason }),
    });
    setBusy(false);
    onResolved(request.idempotency_key);
  }

  const entityLabel =
    request.scope.entity_ref ?? request.scope.team_ref ?? request.scope.user_ref ?? request.scope.level;

  return (
    <Card className="w-full">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <p className="text-sm font-medium leading-none">
              {request.requesting_agent}
            </p>
            <p className="text-xs text-muted-foreground">{request.action}</p>
          </div>
          <div className="flex gap-1.5 shrink-0">
            <Badge variant="secondary">{entityLabel}</Badge>
            <Badge variant="outline">{request.scope.level}</Badge>
          </div>
        </div>

        <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
          {request.rationale}
        </p>
      </CardHeader>

      <CardContent className="pb-3">
        {/* Draft preview — prompt-kit Message component */}
        <Message>
          <MessageAvatar
            src=""
            alt={request.requesting_agent}
            fallback={request.requesting_agent.slice(0, 2).toUpperCase()}
          />
          <MessageContent className="font-mono text-sm whitespace-pre-wrap leading-relaxed flex-1">
            {request.preview}
          </MessageContent>
        </Message>

        {mode === "editing" && (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium text-muted-foreground">Edit draft before approving:</p>
            <Textarea
              rows={6}
              value={editedBody}
              onChange={(e) => setEditedBody(e.target.value)}
              className="font-mono text-sm"
            />
          </div>
        )}

        {mode === "rejecting" && (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium text-muted-foreground">Reason for rejection:</p>
            <Textarea
              rows={3}
              placeholder="Explain why this action should not proceed…"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
          </div>
        )}
      </CardContent>

      <CardFooter className="gap-2 pt-0">
        {mode === "idle" && (
          <>
            <Button
              size="sm"
              disabled={busy}
              onClick={() => handleApprove()}
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setMode("editing")}
            >
              Edit &amp; Approve
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={busy}
              onClick={() => setMode("rejecting")}
            >
              Reject
            </Button>
          </>
        )}

        {mode === "editing" && (
          <>
            <Button
              size="sm"
              disabled={busy}
              onClick={() => handleApprove(editedBody)}
            >
              Approve with edits
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => { setMode("idle"); setEditedBody(request.preview); }}
            >
              Cancel
            </Button>
          </>
        )}

        {mode === "rejecting" && (
          <>
            <Button
              size="sm"
              variant="destructive"
              disabled={busy || !rejectReason.trim()}
              onClick={handleReject}
            >
              Confirm rejection
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => { setMode("idle"); setRejectReason(""); }}
            >
              Cancel
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
}
