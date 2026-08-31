/**
 * Recruiter batch-upload dashboard.
 * Owner: Person 1 (M.1)
 *
 * Responsibilities:
 *  - Allow a recruiter to upload a ZIP archive (≤ 50 MB) + structured job rubric.
 *  - POST to /api/jobs/upload → receive batch_id + status_url.
 *  - Show real-time progress via <StatusPoller>.
 *  - Link to /recruiter/leaderboard once processing is complete.
 */
"use client";

import { UploadForm } from "@/components/UploadForm";
import { StatusPoller } from "@/components/StatusPoller";
import { useState } from "react";

export default function RecruiterPage() {
  const [batchId, setBatchId] = useState<string | null>(null);

  // TODO (Person 1 — M.1): Implement recruiter dashboard UI.

  return (
    <main>
      <h1>Recruiter Dashboard</h1>
      {!batchId ? (
        <UploadForm role="recruiter" onSuccess={(id) => setBatchId(id)} />
      ) : (
        <StatusPoller batchId={batchId} />
      )}
    </main>
  );
}
