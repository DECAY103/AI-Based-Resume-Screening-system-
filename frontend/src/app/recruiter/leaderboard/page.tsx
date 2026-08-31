/**
 * Recruiter leaderboard — sortable ranked results view.
 * Owner: Person 1 (M.10)
 *
 * Responsibilities:
 *  - Read batch_id from search params.
 *  - Fetch GET /api/jobs/{batch_id}/results.
 *  - Render <Leaderboard> component with sort/filter controls.
 *  - Show detail modal on row click (score breakdown + skill gaps).
 *  - Separate section for pre-filtered candidates.
 */
"use client";

import { Leaderboard } from "@/components/Leaderboard";
import { useSearchParams } from "next/navigation";

export default function LeaderboardPage() {
  const params = useSearchParams();
  const batchId = params.get("batch_id") ?? "";

  // TODO (Person 1 — M.10): Implement leaderboard page UI.

  return (
    <main>
      <h1>Candidate Leaderboard</h1>
      <Leaderboard batchId={batchId} />
    </main>
  );
}
