/**
 * Date display in the wireframes' form ("26 Sep 2026", "26 Sep 10:40"). Months are spelt out here
 * rather than through Intl, whose en-GB output ("Sept") differs between runtimes. Times are shown
 * in IST, ZongoVita's zone.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const IST_OFFSET_MINUTES = 330;
const DAY_MS = 86_400_000;

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

/** "2026-09-26T05:10:00Z" -> "26 Sep 10:40". */
export function formatDayTime(iso: string): string {
  const p = parts(iso);
  return `${p.day} ${p.month} ${p.time}`;
}

/** The instant ``days`` whole days after ``iso``, as ISO 8601. */
export function addDays(iso: string, days: number): string {
  return new Date(new Date(iso).getTime() + days * DAY_MS).toISOString();
}

/** Whole days from ``now`` until ``iso`` (0 when it has passed). */
export function daysUntil(iso: string, now = Date.now()): number {
  return Math.max(0, Math.ceil((new Date(iso).getTime() - now) / DAY_MS));
}
