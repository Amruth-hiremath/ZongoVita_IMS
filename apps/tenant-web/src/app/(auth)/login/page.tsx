import { NoticeProvider } from "@ims/ui";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getSession } from "@/session/server";

import { LoginCard } from "./login-card";

export const metadata: Metadata = { title: "Sign in" };

/** F03 Login. */
export default async function LoginPage() {
  if (await getSession()) redirect("/dashboard");
  return (
    <NoticeProvider>
      <main className="flex min-h-screen flex-col items-center justify-center bg-white px-4 py-10">
        <LoginCard />
      </main>
    </NoticeProvider>
  );
}
