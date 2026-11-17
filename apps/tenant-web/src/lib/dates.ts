/**
 * Date display in the wireframes' form ("26 Sep 2026", "26 Sep 10:40"). Months are spelt out here rather than through Intl, whose en-GB output
 * ("Sept") differs between runtimes. Times are shown in IST, the customer's zone in the frames.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const IST_OFFSET_MINUTES = 330;

function parts(iso: string): { day: string; month: string; year: number; time: string } {
  // A bare date ("2026-09-26") is a calendar day; a timestamp is shifted to IST.
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(iso);
  const date = new Date(dateOnly ? `${iso}T00:00:00Z` : iso);
  if (!dateOnly) date.setUTCMinutes(date.getUTCMinutes() + IST_OFFSET_MINUTES);
  return {
    day: String(date.getUTCDate()).padStart(2, "0"),
    month: MONTHS[date.getUTCMonth()] ?? "",
    year: date.getUTCFullYear(),
    time: `${String(date.getUTCHours()).padStart(2, "0")}:${String(date.getUTCMinutes()).padStart(2, "0")}`,
  };
}

/** "2026-09-26" -> "26 Sep 2026". */
export function formatDay(iso: string): string {
  const p = parts(iso);
  return `${p.day} ${p.month} ${p.year}`;
}

/** "2026-09-26" -> "26 Sep". */
export function formatDayShort(iso: string): string {
  const p = parts(iso);
  return `${p.day} ${p.month}`;
}

/** "2026-09-26T05:10:00Z" -> "26 Sep 10:40". */
export function formatDayTime(iso: string): string {
  const p = parts(iso);
  return `${p.day} ${p.month} ${p.time}`;
}

/** "2026-09-26T04:35:00Z" -> "26 Sep 2026 · 10:05". */
export function formatDayYearTime(iso: string): string {
  const p = parts(iso);
  return `${p.day} ${p.month} ${p.year} · ${p.time}`;
}

/** "2024-03" or "2024-03-01" -> "Mar 2024". */
export function formatMonth(iso: string): string {
  const p = parts(iso.length === 7 ? `${iso}-01` : iso);
  return `${p.month} ${p.year}`;
}
