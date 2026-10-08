/**
 * Login page — credential submission + 2FA initiation.
 * Owner: Person 1 (M.2)
 *
 * Responsibilities:
 *  - Collect email + password.
 *  - POST to /api/auth/login → receive temp_token.
 *  - Redirect to /auth/verify with temp_token in state.
 *  - In register mode, show password strength meter and block weak passwords.
 *  - Link to password reset / forgot password flow.
 */
"use client";

import { useState } from "react";
import { authApi } from "@/lib/api";
import type { PasswordStrength } from "@/lib/api";
import { useRouter } from "next/navigation";
import { PasswordStrengthMeter } from "@/components/PasswordStrengthMeter";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [registerMode, setRegisterMode] = useState(false);
  const [role, setRole] = useState<"candidate" | "recruiter">("recruiter");
  const [setupUri, setSetupUri] = useState<string | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<PasswordStrength | null>(null);

  const registerDisabled = registerMode && (!passwordStrength || !passwordStrength.is_acceptable);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      if (registerMode) {
        if (registerDisabled) {
          setError("Password is too weak. Please strengthen it before creating your account.");
          return;
        }
        const data = await authApi.register(email, password, role);
        setSetupUri(data.otpauth_uri);
        return;
      }
      const { temp_token } = await authApi.login(email, password);
      router.push(`/auth/verify?temp_token=${temp_token}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <main className="shell"><section className="upload-card auth-card">
      <p className="eyebrow">Resume Screening</p>
      <h1>{registerMode ? "Create an account" : "Welcome back"}</h1>
      <p>{registerMode ? "Use an authenticator app to scan or add the setup URI shown after registration." : "Sign in, then enter your authenticator app code."}</p>
      <form className="form-stack" onSubmit={handleSubmit}>
        <div><label className="field-label" htmlFor="email">Email address</label><input id="email" type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} required /></div>
        <div>
          <label className="field-label" htmlFor="password">Password</label>
          <input id="password" type="password" placeholder="At least 8 characters" value={password} onChange={(e) => setPassword(e.target.value)} required />
          {registerMode && <PasswordStrengthMeter password={password} onChange={setPasswordStrength} />}
        </div>
        {registerMode && <div><label className="field-label" htmlFor="account-role">Account type</label><select id="account-role" value={role} onChange={(e) => setRole(e.target.value as typeof role)}><option value="recruiter">Recruiter</option><option value="candidate">Candidate</option></select></div>}
        {error && <p className="message error-message" role="alert">{error}</p>}
        <button className="primary" id="login-submit" type="submit" disabled={registerDisabled}>{registerMode ? "Create account" : "Continue"}</button>
      </form>
      {setupUri && <><h2>Authenticator setup URI</h2><code className="setup-uri">{setupUri}</code><p>After adding it to your authenticator app, switch to sign in.</p></>}
      <div className="auth-footer-links">
        <button className="link-button" onClick={() => { setRegisterMode(!registerMode); setSetupUri(null); setError(null); }}>{registerMode ? "Already have an account? Sign in" : "New here? Create an account"}</button>
        {!registerMode && <button className="link-button forgot-link" onClick={() => router.push("/auth/forgot-password")}>Forgot password?</button>}
      </div>
    </section></main>
  );
}
