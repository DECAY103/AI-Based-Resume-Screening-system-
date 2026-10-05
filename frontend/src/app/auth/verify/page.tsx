/**
 * 2FA verification page — step 2 of 2.
 * Owner: Person 1 (M.2)
 *
 * Sends temp_token + the 6-digit code to /api/auth/verify. On success the
 * backend sets the httpOnly login cookie and we go to the role's dashboard.
 */
"use client";

import { useEffect, useState } from "react";
import { authApi } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function VerifyPage() {
  const router = useRouter();
  const [tempToken, setTempToken] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = sessionStorage.getItem("temp_token");
    if (!t) router.replace("/auth/login"); // came here without logging in first
    else setTempToken(t);
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tempToken) return;
    setError(null);
    setBusy(true);
    try {
      const { role } = await authApi.verify(tempToken, code);
      sessionStorage.removeItem("temp_token");
      router.push(role === "recruiter" ? "/recruiter" : "/candidate");
      router.refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setBusy(false);
    }
  }

  if (!tempToken) return <p>Loading…</p>;

  return (
    <main>
      <h1>Two-Factor Verification</h1>
      <p>Enter the 6-digit code we sent you. It expires in 5 minutes.</p>
      <form onSubmit={handleSubmit}>
        <input
          id="2fa-code"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="6-digit code"
          maxLength={6}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          required
        />
        {error && <p role="alert">{error}</p>}
        <button id="verify-submit" type="submit" disabled={busy}>
          {busy ? "Verifying…" : "Verify"}
        </button>
      </form>
    </main>
  );
}
