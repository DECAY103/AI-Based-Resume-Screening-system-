/**
 * middleware.ts — Next.js Edge Middleware for RBAC route protection.
 * Owner: Person 1 (M.2)
 *
 * Rules:
 *  /candidate/*  → requires role: "candidate" or "admin"
 *  /recruiter/*  → requires role: "recruiter" or "admin"
 *  /auth/*       → public (no token needed)
 *
 * TODO (Person 1 — M.2):
 *  - Decode JWT from cookie (use jose or next-auth for edge-compatible JWT decode).
 *  - Check role claim and redirect to /auth/login if missing or wrong role.
 *  - Add token expiry check.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // TODO (Person 1 — M.2): Replace stub with real JWT verification.
  const token = request.cookies.get("access_token")?.value;

  if (!token && !pathname.startsWith("/auth")) {
    return NextResponse.redirect(new URL("/auth/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/candidate/:path*", "/recruiter/:path*"],
};
