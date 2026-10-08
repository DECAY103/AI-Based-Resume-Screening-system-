/**
 * 2FA verification page.
 * Owner: Person 1 (M.2)
 *
 * Responsibilities:
 *  - Read temp_token from search params.
 *  - Accept 6-digit 2FA code from user.
 *  - POST to /api/auth/verify → receive access_token + role + last_login_at.
 *  - Store JWT in httpOnly cookie (via API route or set-cookie header).
 *  - Show last login timestamp before redirecting.
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
  const [lastLogin, setLastLogin] = useState<string | null>(null);
  const [redirecting, setRedirecting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const { role, last_login_at } = await authApi.verify(tempToken, code);
      if (last_login_at) {
        setLastLogin(last_login_at);
        setRedirecting(true);
        // Show last-login for 2.5 seconds before redirecting
        setTimeout(() => {
          router.push(role === "recruiter" ? "/recruiter" : "/candidate");
        }, 2500);
      } else {
        router.push(role === "recruiter" ? "/recruiter" : "/candidate");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Verification failed");
    }
  }

  if (redirecting && lastLogin) {
    const formatted = new Date(lastLogin).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
    return (
      <main className="shell"><section className="upload-card auth-card">
        <p className="eyebrow">Session verified</p>
        <h1>Welcome back!</h1>
        <div className="last-login-banner">
          <span className="last-login-icon">🕐</span>
          <div>
            <p className="last-login-label">Your last login was</p>
            <p className="last-login-time">{formatted}</p>
          </div>
        </div>
        <p className="field-help" style={{ marginTop: 16 }}>Redirecting to your dashboard…</p>
      </section></main>
    );
  }

  return (
    <main className="shell"><section className="upload-card auth-card">
      <p className="eyebrow">Account security</p>
      <h1>Two-Factor Verification</h1>
      <p>Enter the current six-digit code from your authenticator app.</p>
      <form className="form-stack" onSubmit={handleSubmit}>
        <div><label className="field-label" htmlFor="2fa-code">Verification code</label><input id="2fa-code" type="text" inputMode="numeric" autoComplete="one-time-code" placeholder="000000" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} required /></div>
        {error && <p className="message error-message" role="alert">{error}</p>}
        <button className="primary" id="verify-submit" type="submit">Verify</button>
      </form>
    </section></main>
  );
}

export default function VerifyPage() {
  return <Suspense fallback={<main className="shell"><p>Loading verification…</p></main>}><VerifyForm /></Suspense>;
}
