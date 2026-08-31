/**
 * Login page — credential submission + 2FA initiation.
 * Owner: Person 1 (M.2)
 *
 * Responsibilities:
 *  - Collect email + password.
 *  - POST to /api/auth/login → receive temp_token.
 *  - Redirect to /auth/verify with temp_token in state.
 */
"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    // TODO (Person 1 — M.2): Call authApi.login, store temp_token, redirect to /auth/verify.
    try {
      const { temp_token } = await authApi.login(email, password);
      router.push(`/auth/verify?temp_token=${temp_token}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <main>
      <h1>Sign In</h1>
      <form onSubmit={handleSubmit}>
        <input
          id="email"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          id="password"
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        {error && <p role="alert">{error}</p>}
        <button id="login-submit" type="submit">Continue</button>
      </form>
    </main>
  );
}
