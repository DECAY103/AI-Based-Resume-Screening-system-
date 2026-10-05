/**
 * middleware.ts — Next.js Edge Middleware for RBAC route protection.
 * Owner: Person 1 (M.2)
 *
 * Rules:
 *  /candidate/*  → role "candidate" or "admin"
 *  /recruiter/*  → role "recruiter" or "admin"
 *  /             → sends you to your dashboard (or login)
 *  /auth/*       → public
 *
 * The login cookie is a JWT signed by the backend. It is verified here with the
 * shared JWT_SECRET (signature, expiry, token type). The backend re-checks every
 * API call, so this middleware is for navigation only, not the security boundary.
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

const COOKIE = "access_token";

type Session = { role: string };

async function readSession(request: NextRequest): Promise<Session | null> {
  const token = request.cookies.get(COOKIE)?.value;
  if (!token) return null;

  const secret = process.env.JWT_SECRET;
  if (!secret) {
    console.error("[middleware] JWT_SECRET is missing from frontend/.env.local");
    return null;
  }

  try {
    const { payload } = await jwtVerify(token, new TextEncoder().encode(secret), {
      algorithms: ["HS256"],
    });
    if (payload.type !== "access" || typeof payload.role !== "string") return null;
    return { role: payload.role };
  } catch {
    return null; // bad signature or expired
  }
}

function homeFor(role: string): string {
  return role === "recruiter" ? "/recruiter" : "/candidate";
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const session = await readSession(request);

  if (!session) {
    return NextResponse.redirect(new URL("/auth/login", request.url));
  }

  if (pathname === "/") {
    return NextResponse.redirect(new URL(homeFor(session.role), request.url));
  }

  const isAdmin = session.role === "admin";
  if (pathname.startsWith("/recruiter") && !isAdmin && session.role !== "recruiter") {
    return NextResponse.redirect(new URL(homeFor(session.role), request.url));
  }
  if (pathname.startsWith("/candidate") && !isAdmin && session.role !== "candidate") {
    return NextResponse.redirect(new URL(homeFor(session.role), request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/candidate/:path*", "/recruiter/:path*"],
};
