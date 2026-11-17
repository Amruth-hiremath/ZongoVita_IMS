"use client";

import { Button, Input, useNotice } from "@ims/ui";
import { useState, type FormEvent, type ReactNode } from "react";

import { signInAsFixturePersona } from "@/session/actions";

type Mode = "core" | "fixtures";
type Step = { kind: "idle" } | { kind: "busy" } | { kind: "failed"; message: string } | { kind: "password_accepted"; enrolment: boolean };

/**
 * F03, drawn as in the wireframe.
 *
 * Signed in to IMS Core (`core` mode) the card submits the work email and password to the BFF
 * (POST /bff/auth/login, LLD 6.2). Every sign-in then needs the authenticator step (LD-79), and
 * that screen, like enrolment and activation, has no approved design yet (U-06): the card says
 * so rather than inventing one. The wireframe's "Sign in as Type 2 / Type 3" pair becomes one
 * "Sign in", because what a person may do comes from their role assignments, not from a choice
 * made at sign-in (LLD 7; Docs/UI_Implementation.md section 10).
 *
 * In `fixtures` mode the two buttons choose a sample persona, as before; no credential is checked.
 * "Continue with Company SSO" only explains itself: SSO is Phase 2 (AD-23).
 */
export function LoginCard({ mode }: { mode: Mode }) {
  const notify = useNotice();
  const [step, setStep] = useState<Step>({ kind: "idle" });

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setStep({ kind: "busy" });
    const response = await fetch("/bff/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json", "x-ims-csrf": "1" },
      body: JSON.stringify({ login_identifier: form.get("email"), password: form.get("password") }),
    }).catch(() => null);
    if (response?.ok) {
      const body = (await response.json()) as { status: string };
      setStep({ kind: "password_accepted", enrolment: body.status === "mfa_enrolment_required" });
    } else if (response?.status === 429 || response?.status === 503) {
      setStep({ kind: "failed", message: "Sign-in is busy. Try again in a moment." });
    } else {
      setStep({ kind: "failed", message: "Sign-in failed. Check your work email and password." });
    }
  }

  const fields: ReactNode = (
    <>
      <label htmlFor="email" className="label-caps mb-1.5 block">
        Work email
      </label>
      <Input id="email" name="email" type="email" autoComplete="username" placeholder="name@zongovita.in" required={mode === "core"} />

      <label htmlFor="password" className="label-caps mb-1.5 mt-5 block">
        Password
      </label>
      <Input
        id="password"
        name="password"
        type="password"
        autoComplete="current-password"
        placeholder="••••••••••"
        required={mode === "core"}
      />

      <button
        type="button"
        className="mt-4 text-[12.5px] text-blue-600 hover:underline"
        onClick={() =>
          notify(
            "Password reset is not available",
            "The current design has no password reset. Ask your Type 1 admin for help (F22).",
          )
        }
      >
        Forgot password?
      </button>
    </>
  );

  const card = (children: ReactNode) => (
    <>
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
        {children}

        <p className="mt-[46px] border-t border-gray-200 pt-4 text-[11.5px] text-gray-500">
          Need an account? Ask your Type 1 admin (F22).
        </p>
      </div>
    </>
  );

  const frame = "w-full max-w-[440px] overflow-hidden rounded-[10px] border-[1.4px] border-gray-300 bg-white";

  if (mode === "core") {
    return (
      <form onSubmit={signIn} className={frame} aria-label="Sign in">
        {card(
          <>
            {fields}
            <Button type="submit" variant="primary" disabled={step.kind === "busy"} className="mt-3.5 h-[42px] w-full text-[13.5px]">
              Sign in
            </Button>
            {step.kind === "failed" ? (
              <p role="alert" className="mt-3 text-[12px] text-red-700">
                {step.message}
              </p>
            ) : null}
            {step.kind === "password_accepted" ? (
              <div role="status" className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-[12px] leading-[18px] text-amber-800">
                <p className="font-semibold">Password accepted</p>
                <p className="mt-1">
                  {step.enrolment
                    ? "The next step is setting up an authenticator app, which every account needs (LD-79)."
                    : "The next step is the code from your authenticator app, which every sign-in needs (LD-79)."}{" "}
                  That screen has no approved design yet, so sign-in cannot be completed here.
                </p>
              </div>
            ) : null}
          </>,
        )}
      </form>
    );
  }

  return (
    <>
      <form action={signInAsFixturePersona} className={frame}>
        {card(
          <>
            {fields}
            <div className="mt-3.5 grid grid-cols-2 gap-2">
              <Button type="submit" name="persona" value="type2" variant="primary" className="h-[42px] text-[13.5px]">
                Sign in as Type 2
              </Button>
              <Button type="submit" name="persona" value="type3" variant="primary" className="h-[42px] text-[13.5px]">
                Sign in as Type 3
              </Button>
            </div>
          </>,
        )}
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
