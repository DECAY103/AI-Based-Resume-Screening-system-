/**
 * Candidate upload portal.
 * Owner: Person 1 (M.1)
 *
 * Responsibilities:
 *  - Allow a candidate to select a job and upload a single PDF résumé (≤ 5 MB).
 *  - POST to /api/candidates/upload → receive batch_id + status_url.
 *  - Render <StatusPoller> beside the upload form to poll /api/jobs/{batch_id}/status until complete.
 *  - Display final evaluation result to the candidate.
 */
"use client";

import { UploadForm } from "@/components/UploadForm";
import { StatusPoller } from "@/components/StatusPoller";
import { useState } from "react";

export default function CandidatePage() {
  const [batchId, setBatchId] = useState<string | null>(null);

  return (
    <main className="shell">
      <header className="hero"><p className="eyebrow">Candidate portal</p><h1>Submit your résumé.</h1><p>Enter the recruiter batch ID and upload a PDF. Your résumé is anonymised before it is evaluated.</p></header>
      <div className={`split-layout${batchId ? " split-layout--has-result" : ""}`}>
        <div className="split-layout__upload">
          <UploadForm role="candidate" onSuccess={(id) => setBatchId(id)} />
        </div>
        {batchId && (
          <div className="split-layout__result">
            <StatusPoller batchId={batchId} role="candidate" />
          </div>
        )}
      </div>
    </main>
  );
}
