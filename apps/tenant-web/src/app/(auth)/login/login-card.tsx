"use client";

import { Button, Input, useNotice } from "@ims/ui";

import { signInAsFixturePersona } from "@/session/actions";

/**
 * F03. The card is drawn as in the wireframe. What its buttons do today:
 *
 * - "Sign in as Type 2 / Type 3" choose a FIXTURE persona. No credential is checked, because
 *   Core has no login yet. With identity in place these become one "Sign in" submit to
 *   POST /ui/v1/auth/login, followed by the MFA step the LLD requires (LD-79).
 * - "Continue with Company SSO" only explains itself: SSO is Phase 2 (AD-23).
 */
export function LoginCard() {
  const notify = useNotice();
  return (
    <>
      <form
        action={signInAsFixturePersona}
        className="w-full max-w-[440px] overflow-hidden rounded-[10px] border-[1.4px] border-gray-300 bg-white"
      >
        <div aria-hidden className="h-1 bg-blue-600" />
        <div className="px-[27px] pb-7 pt-9">
          <div className="flex flex-col items-center text-center">
            <span className="flex size-12 items-center justify-center rounded-[10px] bg-gray-900 text-[20px] font-bold text-white">
              I
            </span>
            <h1 className="mt-4 text-[18px] font-bold text-gray-900">IMS</h1>
            <p className="mt-2 text-[12.5px] text-gray-500">Inventory Management · Web App</p>
          </div>

          <Button
            variant="primary"
            className="mt-[52px] h-11 w-full text-[13.5px]"
            onClick={() =>
              notify("Company SSO is not available yet", "Single sign-on (OIDC / SAML) is planned for Phase 2 (AD-23).")
            }
          >
            Continue with Company SSO
          </Button>

          <p className="py-3 text-center text-[11px] text-gray-400">— or —</p>

          <label htmlFor="email" className="label-caps mb-1.5 block">
            Work email
          </label>
          <Input id="email" name="email" type="email" autoComplete="username" placeholder="name@zongovita.in" />

          <label htmlFor="password" className="label-caps mb-1.5 mt-5 block">
            Password
          </label>
          <Input id="password" name="password" type="password" autoComplete="current-password" placeholder="••••••••••" />

          <button
            type="button"
            className="mt-4 text-[12.5px] text-blue-600 hover:underline"
            onClick={() =>
              notify("Not connected yet", "Password reset needs the identity endpoints, which IMS Core does not provide yet.")
            }
          >
            Forgot password?
          </button>

          <div className="mt-3.5 grid grid-cols-2 gap-2">
            <Button type="submit" name="persona" value="type2" variant="primary" className="h-[42px] text-[13.5px]">
              Sign in as Type 2
            </Button>
            <Button type="submit" name="persona" value="type3" variant="primary" className="h-[42px] text-[13.5px]">
              Sign in as Type 3
            </Button>
          </div>

          <p className="mt-[46px] border-t border-gray-200 pt-4 text-[11.5px] text-gray-500">
            Need an account? Ask your Type 1 admin (F22).
          </p>
        </div>
      </form>

      {/* Outside the wireframe card: the frames include Type 1 screens but no way to reach them. */}
      <form action={signInAsFixturePersona} className="mt-4 text-center text-[11px] text-gray-500">
        Sample data mode ·{" "}
        <button type="submit" name="persona" value="type1" className="text-blue-600 hover:underline">
          view the Type 1 screens
        </button>
      </form>
    </>
  );
}
