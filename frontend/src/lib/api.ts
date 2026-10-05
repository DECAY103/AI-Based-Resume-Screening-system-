/**
 * api.ts — typed API client for the FastAPI backend.
 * Owner: Person 1 (M.1, M.2, M.10)
 *
 * All requests go through /api/* which next.config.js proxies to the backend.
 * Add the Authorization header by reading the JWT from cookies/localStorage
 * once auth is implemented.
 *
 * TODO (Person 1): Replace placeholder implementations with real fetch calls.
 */

const BASE = "/api";

// ─── Shared types ────────────────────────────────────────────────────────────

export interface BatchStatus {
  batch_id: string;
  status: "queued" | "extracting" | "scoring" | "pre_filtered" | "completed" | "failed";
  total_files: number;
  processed_files: number;
  failed_files: number;
  pre_filtered_count: number;
  progress_percentage: number;
}

export interface CandidateResult {
  candidate_id: string;
  overall_score: number;
  skill_match_score: number;
  work_experience_score: number;
  matching_skills: string[];
  missing_skills: string[];
  verdict_summary: string;
  cosine_similarity_score: number;
  status: "completed" | "pre_filtered";
}

export interface ProcessingFileResult {
  filename: string;
  status: "accepted" | "rejected" | "failed";
  validation_passed: boolean;
  extracted_text: string | null;
  anonymised_text: string | null;
  safety_passed: boolean | null;
  safety_reason: string | null;
  error: string | null;
}

export interface ProcessingResult {
  input_type: "pdf" | "zip";
  total_files: number;
  accepted_files: number;
  rejected_files: number;
  files: ProcessingFileResult[];
}

// ─── Helper ───────────────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: {
      // TODO (Person 1 — M.2): Attach JWT here.
      // Authorization: `Bearer ${getToken()}`,
      ...init?.headers,
    },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || res.statusText);
  }
  return res.json() as Promise<T>;
}

// ─── Auth API (M.2) ───────────────────────────────────────────────────────────

export const authApi = {
  register: (email: string, password: string, role: "candidate" | "recruiter") =>
    request<{ message: string; otpauth_uri: string }>("/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, role }),
    }),
  login: (email: string, password: string) =>
    request<{ temp_token: string }>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  verify: (temp_token: string, code: string) =>
    request<{ access_token: string; token_type: string; role: string }>("/auth/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ temp_token, code }),
    }),
};

// ─── Candidates API (M.1 / M.3) ──────────────────────────────────────────────

export const candidatesApi = {
  /** Upload a single PDF résumé. Returns batch_id. */
  upload: async (file: File, jobId: string): Promise<string> => {
    const form = new FormData();
    form.append("file", file);
    form.append("job_id", jobId);
    const data = await request<{ batch_id: string }>("/candidates/upload", {
      method: "POST",
      body: form,
    });
    return data.batch_id;
  },
};

// ─── Jobs API (M.3 / M.9 / M.10) ────────────────────────────────────────────

export const jobsApi = {
  /** Upload a ZIP batch + rubric. Returns batch_id. */
  uploadBatch: async (file: File, rubric: string): Promise<string> => {
    const form = new FormData();
    form.append("file", file);
    form.append("rubric", rubric);
    const data = await request<{ batch_id: string }>("/jobs/upload", {
      method: "POST",
      body: form,
    });
    return data.batch_id;
  },

  getStatus: (batchId: string) =>
    request<BatchStatus>(`/jobs/${batchId}/status`),

  getResults: async (batchId: string): Promise<CandidateResult[]> => {
    const data = await request<{ batch_id: string; results: CandidateResult[] }>(
      `/jobs/${batchId}/results`
    );
    return data.results;
  },
};

// ─── Ingestion & sanitisation preview (M.3 – M.6) ───────────────────────────

export const processingApi = {
  /** Run the Person 2 pipeline and return its direct, displayable output. */
  preview: async (file: File): Promise<ProcessingResult> => {
    const form = new FormData();
    form.append("file", file);
    return request<ProcessingResult>("/processing/preview", {
      method: "POST",
      body: form,
    });
  },
};
