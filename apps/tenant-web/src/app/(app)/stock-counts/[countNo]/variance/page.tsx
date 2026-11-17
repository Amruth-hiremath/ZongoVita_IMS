import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { getVarianceReview } from "@/data/stock-counts";
import { requireSession } from "@/session/server";

import { VarianceReviewScreen } from "../../variance-review";

export async function generateMetadata({ params }: { params: Promise<{ countNo: string }> }): Promise<Metadata> {
  const { countNo } = await params;
  return { title: `Variance Review — ${decodeURIComponent(countNo)}` };
}

/** F17 Variance Review for one count session. */
export default async function VariancePage({ params }: { params: Promise<{ countNo: string }> }) {
  const { countNo } = await params;
  const [{ me }, review] = await Promise.all([requireSession(), getVarianceReview(decodeURIComponent(countNo))]);
  if (review === null) notFound();
  return <VarianceReviewScreen me={me} review={review} />;
}
