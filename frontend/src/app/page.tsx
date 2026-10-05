/**
 * Landing page — redirects authenticated users to their role-appropriate dashboard.
 * Owner: Person 1 (M.1)
 */
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/processing");
}
