/**
 * StatusPoller — polls the batch status endpoint until completion.
 * Owner: Person 1 (M.1)
 *
 * Props:
 *  - batchId: UUID string returned from the upload endpoint.
 *
 * Behaviour:
 *  - Calls GET /api/jobs/{batchId}/status on an interval (e.g. every 3 s).
 *  - Displays a progress bar using `progress_percentage`.
 *  - Stops polling when status is "completed" or "failed".
 *  - On completion, shows a link to the leaderboard (recruiter) or result summary (candidate).
 *
 * TODO (Person 1 — M.1):
 *  - Implement polling interval with cleanup on unmount.
 *  - Show per-file counts (total / processed / failed / pre_filtered).
 *  - Handle "failed" status gracefully with error message.
 */
"use client";

import { useEffect, useState } from "react";
import { jobsApi, type BatchStatus } from "@/lib/api";

interface StatusPollerProps {
  batchId: string;
}

export function StatusPoller({ batchId }: StatusPollerProps) {
  const [status, setStatus] = useState<BatchStatus | null>(null);

  useEffect(() => {
    // TODO (Person 1 — M.1): Replace stub with real polling logic.
    const interval = setInterval(async () => {
      const data = await jobsApi.getStatus(batchId);
      setStatus(data);
      if (data.status === "completed" || data.status === "failed") {
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [batchId]);

  if (!status) return <p>Initialising…</p>;

  return (
    <div>
      <p>Status: {status.status}</p>
      <p>Progress: {status.progress_percentage.toFixed(1)}%</p>
      <p>
        {status.processed_files} / {status.total_files} processed
        {status.failed_files > 0 && ` · ${status.failed_files} failed`}
      </p>
    </div>
  );
}
