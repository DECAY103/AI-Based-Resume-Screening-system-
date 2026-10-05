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

import { useEffect, useMemo, useState } from "react";
import { jobsApi, type CandidateResult } from "@/lib/api";

interface LeaderboardProps {
  batchId: string;
}

export function Leaderboard({ batchId }: LeaderboardProps) {
  const [results, setResults] = useState<CandidateResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<CandidateResult | null>(null);
  const [sortBy, setSortBy] = useState<"overall_score" | "skill_match_score" | "work_experience_score">("overall_score");

  useEffect(() => {
    jobsApi.getResults(batchId).then(setResults).catch((err) => setError(err instanceof Error ? err.message : "Could not load results.")).finally(() => setLoading(false));
  }, [batchId]);

  const completed = useMemo(() => results.filter((r) => r.status === "completed").sort((a, b) => b[sortBy] - a[sortBy]), [results, sortBy]);
  const prefiltered = results.filter((r) => r.status === "pre_filtered");

  if (loading) return <p>Loading results…</p>;
  if (error) return <p role="alert">{error}</p>;

  return (
    <section className="leaderboard">
      <div className="leaderboard-toolbar"><div><p className="eyebrow">Evaluation results</p><h2>Ranked candidates</h2></div><label className="sort-control">Sort by<select value={sortBy} onChange={(e) => setSortBy(e.target.value as typeof sortBy)}><option value="overall_score">Overall score</option><option value="skill_match_score">Skill match</option><option value="work_experience_score">Experience</option></select></label></div>
    {completed.length === 0 ? <p className="empty-state">No completed candidate evaluations are available yet.</p> : <div className="table-wrap"><table>
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
        {completed.map((r, i) => (
          <tr key={r.candidate_id} onClick={() => setSelected(r)}>
            <td>{i + 1}</td>
            <td className="table-score">{r.overall_score.toFixed(1)}</td>
            <td>{r.skill_match_score.toFixed(1)}</td>
            <td>{r.work_experience_score.toFixed(1)}</td>
            <td>{r.status}</td>
          </tr>
        ))}
      </tbody>
    </table></div>}
    {prefiltered.length > 0 && <p className="pre-filter-note">{prefiltered.length} candidate{prefiltered.length === 1 ? " was" : "s were"} pre-filtered below the top-N cutoff.</p>}
    {selected && <div className="modal" role="dialog" aria-modal="true" aria-label="Candidate evaluation"><div><button className="secondary-button modal-close" onClick={() => setSelected(null)}>Close</button><p className="eyebrow">Candidate evaluation</p><h2>Score breakdown</h2><p>{selected.verdict_summary}</p><h3>Matching skills</h3><p>{selected.matching_skills.join(", ") || "None"}</p><h3>Missing skills</h3><p>{selected.missing_skills.join(", ") || "None"}</p><h3>Semantic similarity</h3><p>{selected.cosine_similarity_score.toFixed(3)}</p><a className="primary" href={`/api/jobs/${batchId}/candidates/${selected.candidate_id}/resume`} target="_blank">Open original résumé</a></div></div>}
    </section>
  );
}
