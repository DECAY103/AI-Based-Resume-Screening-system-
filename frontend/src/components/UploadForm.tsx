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

import { ChangeEvent, useState } from "react";
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

  const expectedExtension = role === "candidate" ? ".pdf" : ".zip";
  const maximumBytes = (role === "candidate" ? 5 : 50) * 1024 * 1024;

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setError(null);
    if (!selected) {
      setFile(null);
      return;
    }
    if (!selected.name.toLowerCase().endsWith(expectedExtension)) {
      setFile(null);
      setError(`Select a ${expectedExtension.toUpperCase()} file.`);
      return;
    }
    if (selected.size > maximumBytes) {
      setFile(null);
      setError(`This file is larger than the ${role === "candidate" ? "5 MB" : "50 MB"} limit.`);
      return;
    }
    setFile(selected);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError(null);
    setLoading(true);
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
    <form className="upload-card form-stack" onSubmit={handleSubmit}>
      <div>
        <label className="field-label" htmlFor="file-input">{role === "candidate" ? "Résumé PDF" : "Resume archive"}</label>
        <input
        className="file-control"
        id="file-input"
        type="file"
        accept={role === "candidate" ? ".pdf" : ".zip"}
        onChange={selectFile}
        required
      />
        <label className="file-picker" htmlFor="file-input">
          <span className="file-picker__icon">↑</span>
          <span><strong>{file ? "Choose another file" : `Select a ${expectedExtension.toUpperCase()} file`}</strong><small>{role === "candidate" ? "PDF, maximum 5 MB" : "ZIP of PDFs, maximum 50 MB"}</small></span>
        </label>
        {file && <div className="file-selected"><strong>{file.name}</strong><span>{Math.max(1, Math.round(file.size / 1024))} KB selected</span></div>}
      </div>
      {role === "candidate" && (
        <div><label className="field-label" htmlFor="job-id-input">Recruiter batch ID</label><input id="job-id-input" type="text" placeholder="Paste the recruiter’s batch ID" value={jobId} onChange={(e) => setJobId(e.target.value)} required /><p className="field-help">Ask the recruiter for the batch ID created with the job rubric.</p></div>
      )}
      {role === "recruiter" && (
        <div><label className="field-label" htmlFor="rubric-input">Job rubric</label><textarea id="rubric-input" placeholder={'{\n  "title": "Backend Developer",\n  "required_skills": ["Python", "FastAPI", "PostgreSQL"],\n  "minimum_experience_years": 2\n}'} value={rubric} onChange={(e) => setRubric(e.target.value)} required /><p className="field-help">Use valid JSON. The required skills are used for semantic ranking and the final evaluation.</p></div>
      )}
      {error && <p className="message error-message" role="alert">{error}</p>}
      <div className="upload-actions"><p>{role === "recruiter" ? "Resumes are anonymised before scoring. AI scores are advisory and should be reviewed by a recruiter." : "Your resume is validated and anonymised before it enters the evaluation process."}</p><button className="primary" id="upload-submit" type="submit" disabled={loading || !file}>{loading ? "Uploading…" : role === "recruiter" ? "Start evaluation" : "Submit résumé"}</button></div>
    </form>
  );
}
