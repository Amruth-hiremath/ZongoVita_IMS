import { Card } from "@ims/ui";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { sessionSource } from "@/session/config";
import { getStaffSession } from "@/session/server";

export const metadata: Metadata = { title: "Sign in" };

/**
 * Where an unsigned visitor lands in `platform` mode. The wireframes contain no Platform Console
 * sign-in screen (nor its authenticator, enrolment or activation steps, U-06), so none is
 * invented: the page says so. The BFF's sign-in routes (/bff/auth/login, /bff/auth/mfa,
 * /bff/auth/mfa/enrol, /bff/auth/activate) are in place for the screen once it is designed.
 */
export default async function SignInPage() {
  if (sessionSource() === "fixtures" || (await getStaffSession())) redirect("/overview");
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-white px-4 py-10">
      <div className="w-full max-w-[520px]">
        <h1 className="text-[21px] font-bold leading-7 text-gray-900">IMS Platform Console</h1>
        <Card className="mt-6 p-5">
          <p className="text-[13px] font-semibold text-gray-900">No wireframe for the sign-in screen</p>
          <p className="mt-1.5 text-[12.5px] leading-5 text-gray-500">
            ZongoVita staff sign in to the Platform Service with their password and an authenticator code, which every
            staff account needs (LLD 15). The wireframes contain no Platform Console sign-in, authenticator or
            activation screen, so this page has none yet.
          </p>
        </Card>
      </div>
    </main>
  );
}
