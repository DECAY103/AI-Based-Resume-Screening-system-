/**
 * Landing page — redirects authenticated users to their role-appropriate dashboard.
 * Owner: Person 1 (M.1)
 */
import { redirect } from "next/navigation";

export default function Home() {
  // TODO (Person 1 — M.1): Check auth cookie / session.
  // Redirect candidates  → /candidate
  // Redirect recruiters  → /recruiter
  // Unauthenticated      → /auth/login
  redirect("/auth/login");
}
