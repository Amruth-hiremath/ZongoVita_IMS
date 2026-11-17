/**
 * Licence state as derived by Core from the licence snapshot (AD-78; LLD 6.4). Mirrors
 * ims_contracts.licence.LicenceState.
 *
 * The web app shows a banner in grace (to the super admin) and in read-only (to everyone),
 * hides write actions in read-only, and offers emergency issue to permitted users (LLD 15).
 */
export const LICENCE_STATES = ["active", "grace", "read_only", "suspended", "terminated"] as const;

export type LicenceState = (typeof LICENCE_STATES)[number];
