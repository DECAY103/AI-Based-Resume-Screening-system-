"use client";

import { authApi } from "@/lib/api";
import { useRouter } from "next/navigation";

export function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    try {
      await authApi.logout();
    } finally {
      router.push("/auth/login");
      router.refresh();
    }
  }

  return (
    <button id="logout" type="button" onClick={handleLogout}>
      Sign out
    </button>
  );
}
