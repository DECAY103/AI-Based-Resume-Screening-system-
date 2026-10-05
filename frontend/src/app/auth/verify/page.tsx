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

import { Suspense, useState } from "react";
import { authApi } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";

function VerifyForm() {
  const router = useRouter();
  const params = useSearchParams();
  const tempToken = params.get("temp_token") ?? "";

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { role } = await authApi.verify(tempToken, code);
      router.push(role === "recruiter" ? "/recruiter" : "/candidate");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed");
    }
  }

  return (
    <main className="shell"><section className="upload-card auth-card">
      <p className="eyebrow">Account security</p>
      <h1>Two-Factor Verification</h1>
      <p>Enter the current six-digit code from your authenticator app.</p>
      <form className="form-stack" onSubmit={handleSubmit}>
        <div><label className="field-label" htmlFor="2fa-code">Verification code</label><input id="2fa-code" type="text" inputMode="numeric" autoComplete="one-time-code" placeholder="000000" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required /></div>
        {error && <p role="alert">{error}</p>}
        <button className="primary" id="verify-submit" type="submit">Verify</button>
      </form>
    </section></main>
  );
}

export default function VerifyPage() {
  return <Suspense fallback={<main className="shell"><p>Loading verification…</p></main>}><VerifyForm /></Suspense>;
}
