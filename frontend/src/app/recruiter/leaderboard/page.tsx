"use client";

import { Suspense } from "react";
import { Leaderboard } from "@/components/Leaderboard";
import { useSearchParams } from "next/navigation";

function LeaderboardContent() {
  const params = useSearchParams();
  const batchId = params.get("batch_id") ?? "";

  return (
    <main>
      <h1>Candidate Leaderboard</h1>
      <Leaderboard batchId={batchId} />
    </main>
  );
}

export default function LeaderboardPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <LeaderboardContent />
    </Suspense>
  );
}