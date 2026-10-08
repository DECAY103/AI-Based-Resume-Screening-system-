/**
 * Reset Password page — set a new password using the token from the email link.
 */
"use client";

import { Suspense, useState } from "react";
import { authApi } from "@/lib/api";
import type { PasswordStrength } from "@/lib/api";
import { useSearchParams } from "next/navigation";
import { PasswordStrengthMeter } from "@/components/PasswordStrengthMeter";

function ResetForm() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [passwordStrength, setPasswordStrength] = useState<PasswordStrength | null>(null);

  const submitDisabled = !passwordStrength || !passwordStrength.is_acceptable || loading;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!passwordStrength?.is_acceptable) {
      setError("Password is too weak. Please strengthen it.");
      return;
    }
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const data = await authApi.resetPassword(token, password);
      setMessage(data.message);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <main className="shell"><section className="upload-card auth-card">
        <h1>Invalid link</h1>
        <p>This password reset link is invalid or has expired.</p>
        <p className="auth-footer"><a className="link-button" href="/auth/forgot-password">Request a new reset link</a></p>
      </section></main>
    );
  }

  return (
    <main className="shell"><section className="upload-card auth-card">
      <p className="eyebrow">Account recovery</p>
      <h1>Set a new password</h1>
      <p>Choose a strong password for your account.</p>
      <form className="form-stack" onSubmit={handleSubmit}>
        <div>
          <label className="field-label" htmlFor="new-password">New password</label>
          <input id="new-password" type="password" placeholder="At least 8 characters" value={password} onChange={(e) => setPassword(e.target.value)} required />
          <PasswordStrengthMeter password={password} onChange={setPasswordStrength} />
        </div>
        {error && <p className="message error-message" role="alert">{error}</p>}
        {message && <p className="message success-message" role="status">{message}</p>}
        <button className="primary" type="submit" disabled={submitDisabled}>{loading ? "Resetting…" : "Reset password"}</button>
      </form>
      {message && <p className="auth-footer"><a className="link-button" href="/auth/login">← Sign in with your new password</a></p>}
    </section></main>
  );
}

export default function ResetPasswordPage() {
  return <Suspense fallback={<main className="shell"><p>Loading…</p></main>}><ResetForm /></Suspense>;
}
