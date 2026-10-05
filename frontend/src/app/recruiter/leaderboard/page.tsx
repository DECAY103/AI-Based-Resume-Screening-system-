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
import { Suspense } from "react";

function LeaderboardContent() {
  const params = useSearchParams();
  const batchId = params.get("batch_id") ?? "";

  return (
    <main className="shell">
      <h1>Candidate Leaderboard</h1>
      {batchId ? <Leaderboard batchId={batchId} /> : <p role="alert">A batch ID is required.</p>}
    </main>
  );
}

export default function LeaderboardPage() {
  return <Suspense fallback={<main className="shell"><p>Loading leaderboard…</p></main>}><LeaderboardContent /></Suspense>;
}
