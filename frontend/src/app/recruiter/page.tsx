/**
 * Recruiter batch-upload dashboard.
 * Owner: Person 1 (M.1)
 *
 * Responsibilities:
 *  - Allow a recruiter to upload a ZIP archive (≤ 50 MB) + structured job rubric.
 *  - POST to /api/jobs/upload → receive batch_id + status_url.
 *  - Show real-time progress via <StatusPoller> beside the upload form.
 *  - Link to /recruiter/leaderboard once processing is complete.
 */
"use client";

import { UploadForm } from "@/components/UploadForm";
import { StatusPoller } from "@/components/StatusPoller";
import { useState } from "react";

export default function RecruiterPage() {
  const [batchId, setBatchId] = useState<string | null>(null);

  return (
    <main className="shell">
      <header className="hero"><p className="eyebrow">Recruiter workspace</p><h1>Evaluate a resume batch.</h1><p>Upload a ZIP of PDF resumes and a structured job rubric. The dashboard will show live progress and ranked outcomes.</p></header>
      <div className={`split-layout${batchId ? " split-layout--has-result" : ""}`}>
        <div className="split-layout__upload">
          <UploadForm role="recruiter" onSuccess={(id) => setBatchId(id)} />
        </div>
        {batchId && (
          <div className="split-layout__result">
            <StatusPoller batchId={batchId} />
          </div>
        )}
      </div>
    </main>
  );
}
