/**
 * Candidate upload portal.
 * Owner: Person 1 (M.1)
 *
 * Responsibilities:
 *  - Allow a candidate to select a job and upload a single PDF résumé (≤ 5 MB).
 *  - POST to /api/candidates/upload → receive batch_id + status_url.
 *  - Render <StatusPoller> to poll /api/jobs/{batch_id}/status until complete.
 *  - Display final evaluation result to the candidate.
 */
"use client";

import { UploadForm } from "@/components/UploadForm";
import { StatusPoller } from "@/components/StatusPoller";
import { useState } from "react";

export default function CandidatePage() {
  const [batchId, setBatchId] = useState<string | null>(null);

  // TODO (Person 1 — M.1): Implement full candidate portal UI.

  return (
    <main>
      <h1>Submit Your Résumé</h1>
      {!batchId ? (
        <UploadForm role="candidate" onSuccess={(id) => setBatchId(id)} />
      ) : (
        <StatusPoller batchId={batchId} />
      )}
    </main>
  );
}
