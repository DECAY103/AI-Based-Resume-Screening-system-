/**
 * Register page.
 * Owner: Person 1 (M.2)
 *
 * Creates a candidate or recruiter account. Admin accounts can't be created here.
 */
"use client";

import { useState } from "react";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"candidate" | "recruiter">("candidate");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await authApi.register(email, password, role);
      router.push("/auth/login");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Create Account</h1>
      <form onSubmit={handleSubmit}>
        <input
          id="reg-email"
          type="email"
          placeholder="Email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          id="reg-password"
          type="password"
          placeholder="Password (8–72 characters)"
          autoComplete="new-password"
          minLength={8}
          maxLength={72}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <select
          id="reg-role"
          value={role}
          onChange={(e) => setRole(e.target.value as "candidate" | "recruiter")}
        >
          <option value="candidate">Candidate</option>
          <option value="recruiter">Recruiter</option>
        </select>
        {error && <p role="alert">{error}</p>}
        <button id="reg-submit" type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p>
        Already registered? <Link href="/auth/login">Sign in</Link>
      </p>
    </main>
  );
}
