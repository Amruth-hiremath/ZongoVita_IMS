import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { NoScreen } from "@/components/no-screen";
import { getActiveCountSession, getPendingVarianceReview } from "@/data/stock-counts";
import { requireSession } from "@/session/server";

import { CountSheet } from "./count-sheet";
import { VarianceReviewScreen } from "./variance-review";

export const metadata: Metadata = { title: "Stock Counts" };

/** Stock Counts: F17 Variance Review for the manager, F16 Stock Count sheet for the store. */
export default async function StockCountsPage() {
  const { me, workspace } = await requireSession();

  switch (workspace) {
    case "manager": {
      const review = await getPendingVarianceReview();
      if (review === null) notFound();
      return <VarianceReviewScreen me={me} review={review} />;
    }
    case "store": {
      const session = await getActiveCountSession();
      if (session === null) notFound();
      return <CountSheet me={me} session={session} />;
    }
    default:
      return (
        <NoScreen title="Stock Counts">
          The wireframes draw stock counts for the manager (F17 Variance Review) and the store (F16 Stock Count) only.
        </NoScreen>
      );
  }
}
