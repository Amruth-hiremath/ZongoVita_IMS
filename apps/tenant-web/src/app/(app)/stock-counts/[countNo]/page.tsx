import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getCountSession } from "@/data/stock-counts";
import { requireSession } from "@/session/server";

import { CountSheet } from "../count-sheet";

export async function generateMetadata({ params }: { params: Promise<{ countNo: string }> }): Promise<Metadata> {
  const { countNo } = await params;
  return { title: `Stock Count — ${decodeURIComponent(countNo)}` };
}

/** F16 Stock Count sheet for one count session. */
export default async function CountSessionPage({ params }: { params: Promise<{ countNo: string }> }) {
  const { countNo } = await params;
  const [{ me }, session] = await Promise.all([requireSession(), getCountSession(decodeURIComponent(countNo))]);
  if (session === null) notFound();
  return <CountSheet me={me} session={session} />;
}
