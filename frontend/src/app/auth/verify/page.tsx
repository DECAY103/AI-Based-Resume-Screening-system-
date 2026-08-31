/**
 * 2FA verification page.
 * Owner: Person 1 (M.2)
 *
 * Responsibilities:
 *  - Read temp_token from search params.
 *  - Accept 6-digit 2FA code from user.
 *  - POST to /api/auth/verify → receive access_token + role.
 *  - Store JWT in httpOnly cookie (via API route or set-cookie header).
 *  - Redirect to role-appropriate dashboard.
 */
"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";

export default function VerifyPage() {
  const router = useRouter();
  const params = useSearchParams();
  const tempToken = params.get("temp_token") ?? "";

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    // TODO (Person 1 — M.2): Call authApi.verify, persist JWT, redirect by role.
    try {
      const { role } = await authApi.verify(tempToken, code);
      router.push(role === "recruiter" ? "/recruiter" : "/candidate");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed");
    }
  }

  return (
    <main>
      <h1>Two-Factor Verification</h1>
      <form onSubmit={handleSubmit}>
        <input
          id="2fa-code"
          type="text"
          inputMode="numeric"
          placeholder="6-digit code"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
        />
        {error && <p role="alert">{error}</p>}
        <button id="verify-submit" type="submit">Verify</button>
      </form>
    </main>
  );
}
