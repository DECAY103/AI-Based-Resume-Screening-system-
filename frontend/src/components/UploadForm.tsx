/**
 * UploadForm — reusable file upload component.
 * Owner: Person 1 (M.1)
 *
 * Props:
 *  - role: "candidate" | "recruiter"
 *    Candidate → single PDF upload to /api/candidates/upload
 *    Recruiter → ZIP + rubric JSON upload to /api/jobs/upload
 *  - onSuccess(batchId: string): called after successful submission.
 *
 * TODO (Person 1 — M.1):
 *  - Add drag-and-drop file area.
 *  - Validate file type and size client-side before submitting.
 *  - Display upload progress bar.
 *  - Add job_id selector for candidate role.
 *  - Add rubric JSON textarea / file picker for recruiter role.
 */
"use client";

import { useState } from "react";
import { jobsApi, candidatesApi } from "@/lib/api";

interface UploadFormProps {
  role: "candidate" | "recruiter";
  onSuccess: (batchId: string) => void;
}

export function UploadForm({ role, onSuccess }: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState("");
  const [rubric, setRubric] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setLoading(true);
    // TODO (Person 1 — M.1): Wire up real API calls.
    try {
      let batchId: string;
      if (role === "candidate") {
        batchId = await candidatesApi.upload(file, jobId);
      } else {
        batchId = await jobsApi.uploadBatch(file, rubric);
      }
      onSuccess(batchId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        id="file-input"
        type="file"
        accept={role === "candidate" ? ".pdf" : ".zip"}
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        required
      />
      {role === "candidate" && (
        <input
          id="job-id-input"
          type="text"
          placeholder="Job ID"
          value={jobId}
          onChange={(e) => setJobId(e.target.value)}
          required
        />
      )}
      {role === "recruiter" && (
        <textarea
          id="rubric-input"
          placeholder="Paste job rubric JSON here"
          value={rubric}
          onChange={(e) => setRubric(e.target.value)}
          required
        />
      )}
      {error && <p role="alert">{error}</p>}
      <button id="upload-submit" type="submit" disabled={loading}>
        {loading ? "Uploading…" : "Upload"}
      </button>
    </form>
  );
}
