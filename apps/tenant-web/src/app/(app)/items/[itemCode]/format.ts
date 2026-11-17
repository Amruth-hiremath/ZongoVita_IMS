export { formatDay } from "@/lib/dates";

/** "WH-PUN-02" -> "PUN-02": the short site form F09 uses in its badges. */
export function shortLocation(code: string): string {
  const dash = code.indexOf("-");
  return dash > 0 && code.slice(dash + 1).includes("-") ? code.slice(dash + 1) : code;
}
