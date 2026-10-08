/**
 * Forgot Password page — request a password reset email.
 */
"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);
    try {
      const data = await authApi.forgotPassword(email);
      setMessage(data.message);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell"><section className="upload-card auth-card">
      <p className="eyebrow">Account recovery</p>
      <h1>Reset your password</h1>
      <p>Enter your email address and we&apos;ll send you a link to reset your password.</p>
      <form className="form-stack" onSubmit={handleSubmit}>
        <div><label className="field-label" htmlFor="reset-email">Email address</label><input id="reset-email" type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
        {error && <p className="message error-message" role="alert">{error}</p>}
        {message && <p className="message success-message" role="status">{message}</p>}
        <button className="primary" type="submit" disabled={loading}>{loading ? "Sending…" : "Send reset link"}</button>
      </form>
      <p className="auth-footer"><a className="link-button" href="/auth/login">← Back to sign in</a></p>
    </section></main>
  );
}
