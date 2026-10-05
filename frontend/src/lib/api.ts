/**
 * api.ts — typed API client for the FastAPI backend.
 * Owner: Person 1 (M.1, M.2, M.10)
 *
 * All requests go through /api/* which next.config.js proxies to the backend.
 * Auth is a httpOnly cookie set by the backend, so no token handling lives here.
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

// ─── Helper ───────────────────────────────────────────────────────────────────

/** Turn a FastAPI error body into a readable message. */
function errorMessage(body: string, fallback: string): string {
  try {
    const detail = JSON.parse(body)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg; // validation errors
  } catch {
    /* not JSON */
  }
  return body || fallback;
}

/**
 * The login cookie is httpOnly and same-origin, so the browser attaches it to
 * every /api request automatically. No token handling is needed here.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);

  // Session expired / not logged in → back to login (but not for the auth calls
  // themselves, where a 401 just means "wrong password / wrong code").
  if (res.status === 401 && !path.startsWith("/auth/") && typeof window !== "undefined") {
    window.location.href = "/auth/login";
    throw new Error("Session expired. Please sign in again.");
  }

  if (!res.ok) {
    throw new Error(errorMessage(await res.text(), res.statusText));
  }
  return res.json() as Promise<T>;
}

const JSON_HEADERS = { "Content-Type": "application/json" };

// ─── Auth API (M.2) ───────────────────────────────────────────────────────────

export type Role = "candidate" | "recruiter" | "admin";

export const authApi = {
  register: (email: string, password: string, role: "candidate" | "recruiter") =>
    request<{ message: string }>("/auth/register", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ email, password, role }),
    }),

  login: (email: string, password: string) =>
    request<{ temp_token: string }>("/auth/login", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ email, password }),
    }),

  /** On success the backend also sets the httpOnly access_token cookie. */
  verify: (temp_token: string, code: string) =>
    request<{ access_token: string; token_type: string; role: Role }>("/auth/verify", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ temp_token, code }),
    }),

  me: () => request<{ user_id: string; email: string; role: Role }>("/auth/me"),

  logout: () => request<{ message: string }>("/auth/logout", { method: "POST" }),
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
