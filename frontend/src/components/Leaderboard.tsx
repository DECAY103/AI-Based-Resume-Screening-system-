/**
 * Leaderboard — sortable ranked candidate results table.
 * Owner: Person 1 (M.10)
 *
 * Props:
 *  - batchId: UUID — used to fetch GET /api/jobs/{batchId}/results.
 *
 * Responsibilities:
 *  - Fetch and display the full ranked list of candidates.
 *  - Allow sorting by overall_score, skill_match_score, work_experience_score.
 *  - Show a detail modal/panel on row click with:
 *      verdict_summary, matching_skills, missing_skills.
 *  - Separate section for pre_filtered candidates.
 *
 * TODO (Person 1 — M.10):
 *  - Implement fetch + sorting state.
 *  - Build detail modal component.
 *  - Add skill-gap visualisation (e.g. badge lists).
 *  - Add CSV export button.
 */
"use client";

import { useEffect, useState } from "react";
import { jobsApi, type CandidateResult } from "@/lib/api";

interface LeaderboardProps {
  batchId: string;
}

export function Leaderboard({ batchId }: LeaderboardProps) {
  const [results, setResults] = useState<CandidateResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // TODO (Person 1 — M.10): Implement fetch.
    jobsApi.getResults(batchId).then((data) => {
      setResults(data);
      setLoading(false);
    });
  }, [batchId]);

  if (loading) return <p>Loading results…</p>;

  return (
    <table>
      <thead>
        <tr>
          <th>Rank</th>
          <th>Overall Score</th>
          <th>Skill Match</th>
          <th>Experience</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {results.map((r, i) => (
          <tr key={r.candidate_id}>
            <td>{i + 1}</td>
            <td>{r.overall_score.toFixed(1)}</td>
            <td>{r.skill_match_score.toFixed(1)}</td>
            <td>{r.work_experience_score.toFixed(1)}</td>
            <td>{r.status}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
