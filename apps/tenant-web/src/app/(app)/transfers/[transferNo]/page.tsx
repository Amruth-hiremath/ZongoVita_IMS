import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getTransfer } from "@/data/transfers";
import { requireSession } from "@/session/server";

import { TransferLifecycle } from "../transfer-lifecycle";

export async function generateMetadata({ params }: { params: Promise<{ transferNo: string }> }): Promise<Metadata> {
  const { transferNo } = await params;
  return { title: decodeURIComponent(transferNo) };
}

/** F15 Transfer lifecycle for one transfer. */
export default async function TransferPage({ params }: { params: Promise<{ transferNo: string }> }) {
  const { transferNo } = await params;
  const [{ me }, transfer] = await Promise.all([requireSession(), getTransfer(decodeURIComponent(transferNo))]);
  if (transfer === null) notFound();
  return <TransferLifecycle me={me} transfer={transfer} />;
}
